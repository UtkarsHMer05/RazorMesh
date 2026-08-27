"""Live-ingress E2E tests for the Phase-4 cross-protocol chain.

These tests start the real FastAPI app in a background thread and
make real HTTP requests through the mounted MCP route. They prove
the live cross-protocol ingress end-to-end:

  Positive
    MCP initialize -> tools/call complete_authorized_checkout
    -> UCP -> AP2 -> Firewall -> IR -> Consistency MATCH -> ALLOW

  Negative material mutation
    Same flow with a mutated quantity that the IR cannot accept
    -> MISMATCH / BLOCK -> no provider effect

  Replay
    Identical protocol request repeated
    -> no duplicate authority/effect

  Conflict
    Same idempotency key with changed payload
    -> conflict/reject

The tests require a live PostgreSQL + Redis (the same dev infra the
M49 suite uses). The orchestrator never takes Razorpay secrets, DB
credentials, AP2 private keys, the ExecutionTicket private key, the
payment provider, shell access, or arbitrary networking from the
caller.
"""

from __future__ import annotations

import os
import socket
import threading
import time
from typing import Any

import pytest
import uvicorn
from sqlalchemy import text

from razormesh_api.persistence.db import create_db_engine
from razormesh_api.settings import get_settings


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class _ServerThread(threading.Thread):
    def __init__(self, app: Any, port: int) -> None:
        super().__init__(daemon=True)
        self._config = uvicorn.Config(
            app, host="127.0.0.1", port=port, log_level="warning", lifespan="on"
        )
        self._server = uvicorn.Server(self._config)
        self._ready = threading.Event()

    def run(self) -> None:
        # Signal readiness once the server is up.
        original_startup = self._server.startup

        async def _patched(*args: Any, **kwargs: Any) -> None:
            await original_startup(*args, **kwargs)
            self._ready.set()

        self._server.startup = _patched  # type: ignore[method-assign]
        self._server.run()

    def wait_ready(self, timeout: float = 15.0) -> None:
        self._ready.wait(timeout=timeout)


@pytest.fixture(scope="module")
def live_server():
    """Start the real FastAPI app on a free port for the live-ingress suite.

    We build a fresh FastAPI app here (instead of reusing the global
    one) so the MCP Streamable HTTP session manager gets its own
    lifecycle and doesn't conflict with unit tests that use the
    global app via TestClient.
    """
    from datetime import UTC, datetime

    from fastapi import FastAPI
    from redis import Redis

    from razormesh_api.api.main import HealthBody, ReadyBody
    from razormesh_api.api.routes.audit import router as audit_router
    from razormesh_api.api.routes.buyer import router as buyer_router
    from razormesh_api.api.routes.buyer_drafts import router as buyer_drafts_router
    from razormesh_api.api.routes.catalog import router as catalog_router
    from razormesh_api.api.routes.ops import router as ops_router
    from razormesh_api.api.routes.phase4_acceptance import router as phase4_acceptance_router
    from razormesh_api.api.routes.security_lab import router as security_lab_router
    from razormesh_api.api.routes.webhooks import router as webhooks_router
    from razormesh_api.protocol.ap2_verifier import (
        AP2_TARGET_VERSION,
        export_ap2_test_merchant_pub_jwk,
        generate_ap2_test_merchant_key,
    )
    from razormesh_api.protocol.mcp_server import mount_mcp
    from razormesh_api.protocol.ucp_adapter import (
        RMA_UCP_PROFILE,
        UCP_PROFILE_PATH,
        UCP_TARGET_VERSION,
    )

    app = FastAPI(title="RazorMesh Trust (live-ingress E2E)")
    for r in (
        catalog_router,
        webhooks_router,
        buyer_router,
        buyer_drafts_router,
        audit_router,
        security_lab_router,
        ops_router,
        phase4_acceptance_router,
    ):
        app.include_router(r)

    @app.get("/health", response_model=HealthBody)
    def _health() -> HealthBody:
        return HealthBody(status="ok", time_utc=datetime.now(UTC).isoformat())

    @app.get("/ready", response_model=ReadyBody)
    def _ready() -> ReadyBody:
        s = get_settings()
        eng = create_db_engine(s.database_url)
        rcli = Redis.from_url(s.redis_url, decode_responses=True)
        checks: dict[str, str] = {}
        try:
            with eng.connect() as c:
                c.execute(text("SELECT 1"))
            checks["postgres"] = "ok"
        except Exception as exc:
            checks["postgres"] = type(exc).__name__
        try:
            rcli.ping()
            checks["redis"] = "ok"
        except Exception as exc:
            checks["redis"] = type(exc).__name__
        return ReadyBody(
            status="ok",
            checks=checks,
            payment_provider=s.payment_provider,
            mock_payment_provider=s.payment_provider == "mock",
        )

    @app.get(UCP_PROFILE_PATH, include_in_schema=False)
    def _ucp_wk() -> dict[str, object]:
        return dict(RMA_UCP_PROFILE)

    @app.get("/ucp/profile", include_in_schema=False)
    def _ucp_profile() -> dict[str, object]:
        return dict(RMA_UCP_PROFILE)

    @app.get("/ucp/version", include_in_schema=False)
    def _ucp_version() -> dict[str, str]:
        return {"version": UCP_TARGET_VERSION}

    @app.get("/ap2/jwks", include_in_schema=False)
    def _ap2_jwks() -> dict[str, object]:
        key = generate_ap2_test_merchant_key()
        jwk = export_ap2_test_merchant_pub_jwk(key, kid="razormesh-ap2-test-merchant")
        return {"ap2_version": AP2_TARGET_VERSION, "keys": [jwk]}

    @app.get("/ap2/version", include_in_schema=False)
    def _ap2_version() -> dict[str, str]:
        return {"version": AP2_TARGET_VERSION}

    mount_mcp(app, base_path="/mcp-mount")

    # Seed a merchant + product so the orchestrator has a real product
    # to propose against. The test DB starts empty (conftest wipes).
    from razormesh_api.domain.ids import new_ulid
    from razormesh_api.persistence.db import create_session_factory
    from razormesh_api.persistence.models import Merchant, Product

    engine = create_db_engine(os.environ["DATABASE_URL"])
    session_factory = create_session_factory(engine)
    mid = f"mrc_{new_ulid()}"
    pid = f"prd_{new_ulid()}"
    now = datetime.now(UTC)
    with session_factory() as session:
        session.add(
            Merchant(
                id=mid,
                name="Phase-4 Live-Ingress Test Merchant",
                display_name="Phase-4 Live-Ingress Test Merchant",
                description="synthetic",
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            Product(
                id=pid,
                merchant_id=mid,
                title="Phase-4 Live-Ingress Test Product",
                description="synthetic",
                brand="RazorMesh",
                category="test",
                condition="new",
                price_minor=479900,
                currency="INR",
                shipping_minor=0,
                tax_minor=0,
                fees_minor=0,
                recurring=False,
                recurring_frequency=None,
                image_url="https://example.invalid/test.png",
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()

    port = _free_port()
    server = _ServerThread(app, port)
    server.start()
    server.wait_ready()
    # Give the MCP session manager a moment to start its task group.
    time.sleep(0.3)
    yield f"http://127.0.0.1:{port}", port
    server._server.should_exit = True
    server.join(timeout=5)


def _init_mcp(base_url: str) -> tuple[str, dict[str, Any]]:
    """DEPRECATED legacy path. Modern mode does not require initialize.

    Kept for tests that exercise the legacy compatibility shim alongside
    the modern mode. The Phase-4 acceptance run uses modern mode only.
    """
    import json as _json
    from urllib import request as _r

    req = _r.Request(
        f"{base_url}/mcp-mount/mcp",
        data=_json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2026-07-28",
                    "capabilities": {},
                    "clientInfo": {"name": "live-e2e-legacy", "version": "0.1"},
                },
            }
        ).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
    )
    with _r.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8")
        headers = {k: v for (k, v) in resp.headers.items()}
        session = headers.get("mcp-session-id") or headers.get("Mcp-Session-Id")
        assert session, f"no session id returned; headers={headers}"
        last = ""
        for line in raw.splitlines():
            if line.startswith("data:"):
                last = line[len("data:") :].strip()
        info = _json.loads(last) if last else {}
        return session, info


# ---------------------------------------------------------------------
# MCP 2026-07-28 MODERN mode helpers (no initialize, no session)
# ---------------------------------------------------------------------

MCP_MODERN_VERSION = "2026-07-28"
MCP_META = {
    "io.modelcontextprotocol/protocolVersion": MCP_MODERN_VERSION,
    "io.modelcontextprotocol/clientCapabilities": {},
}


def _modern_request(
    base_url: str,
    *,
    method: str,
    params: dict[str, Any],
    mcp_name: str | None = None,
) -> tuple[int, dict[str, Any], dict[str, str]]:
    """Send a single MCP 2026-07-28 modern per-request envelope.

    Returns (status, body, response_headers). Body is the decoded
    JSON-RPC envelope; the modern response carries no session id.
    """
    import json as _json
    from urllib import request as _r

    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": {
            **params,
            "_meta": {**MCP_META, **params.get("_meta", {})},
        },
    }
    req = _r.Request(
        f"{base_url}/mcp-mount/mcp",
        data=_json.dumps(body).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": MCP_MODERN_VERSION,
            "Mcp-Method": method,
            **({"Mcp-Name": mcp_name} if mcp_name else {}),
        },
    )
    with _r.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8")
        headers = {k: v for (k, v) in resp.headers.items()}
        try:
            payload = _json.loads(raw) if raw else {}
        except (ValueError, RecursionError):
            payload = {"raw": raw}
        return resp.status, payload, headers


def _modern_call_tool(base_url: str, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    status, payload, headers = _modern_request(
        base_url,
        method="tools/call",
        params={"name": name, "arguments": arguments},
        mcp_name=name,
    )
    if status != 200:
        raise RuntimeError(f"tool {name} failed: {status} {payload!r}")
    # Modern response carries no Mcp-Session-Id.
    for h in headers:
        assert "session-id" not in h.lower(), (
            f"modern response must not carry session id; got header {h!r}"
        )
    result = payload.get("result") if isinstance(payload, dict) else None
    if not isinstance(result, dict):
        raise RuntimeError(f"tool {name} returned no result: {payload!r}")
    content = result.get("content", [])
    if not content:
        return {}
    import json as _json

    return _json.loads(content[0].get("text", "{}"))


def _create_fixture_intent(base_url: str) -> str:
    from urllib import request as _r

    req = _r.Request(
        f"{base_url}/buyer/fixture-intent",
        data=b"",
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with _r.urlopen(req, timeout=15) as resp:
        import json as _json

        return _json.loads(resp.read().decode("utf-8"))["intent_id"]


def _catalog_product(base_url: str) -> str:
    import json as _json
    from urllib import request as _r

    with _r.urlopen(f"{base_url}/catalog/products?limit=1", timeout=15) as resp:
        d = _json.loads(resp.read().decode("utf-8"))
        return d["items"][0]["id"]


def _http_get_json(url: str) -> dict[str, Any]:
    import json as _json
    from urllib import request as _r

    with _r.urlopen(url, timeout=15) as resp:
        return _json.loads(resp.read().decode("utf-8"))


# ---------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------


def test_ucp_well_known_discovery(live_server: tuple[str, int]) -> None:
    """UCP 2026-04-08 well-known profile is live and version-pinned."""
    base_url, _ = live_server
    profile = _http_get_json(f"{base_url}/.well-known/ucp")
    assert profile["ucp"]["version"] == "2026-04-08"


def test_ap2_jwks_discovery(live_server: tuple[str, int]) -> None:
    """AP2 v0.2.0 JWKS is live and version-pinned."""
    base_url, _ = live_server
    jwks = _http_get_json(f"{base_url}/ap2/jwks")
    assert jwks["ap2_version"] == "v0.2.0"
    assert jwks["keys"], "no AP2 keys returned"


def test_mcp_modern_server_discover_no_session(live_server: tuple[str, int]) -> None:
    """MCP MODERN A: server/discover works WITHOUT initialize and WITHOUT Mcp-Session-Id."""
    base_url, _ = live_server

    status, payload, headers = _modern_request(base_url, method="server/discover", params={})
    assert status == 200, payload
    result = payload.get("result", payload)
    assert "2026-07-28" in result.get("supportedVersions", [])
    for h in headers:
        assert "session-id" not in h.lower(), (
            f"modern response must not carry session id; got header {h!r}"
        )


def test_mcp_modern_tools_list_without_initialize(live_server: tuple[str, int]) -> None:
    """MCP MODERN B: tools/list works WITHOUT initialize."""
    base_url, _ = live_server
    status, payload, _ = _modern_request(base_url, method="tools/list", params={})
    assert status == 200, payload
    result = payload.get("result", payload)
    names = {t["name"] for t in result.get("tools", [])}
    assert "complete_authorized_checkout" in names


def test_mcp_modern_tools_call_without_initialize(live_server: tuple[str, int]) -> None:
    """MCP MODERN C: tools/call complete_authorized_checkout works WITHOUT initialize."""
    base_url, _ = live_server
    intent_id = _create_fixture_intent(base_url)
    product_id = _catalog_product(base_url)
    result = _modern_call_tool(
        base_url,
        "complete_authorized_checkout",
        {"intent_id": intent_id, "product_id": product_id, "quantity": 1},
    )
    assert result["decision"] == "ALLOW", result
    assert result["mcp_version"] == "2026-07-28"


def test_mcp_modern_no_session_id_in_response(live_server: tuple[str, int]) -> None:
    """MCP MODERN D: Mcp-Session-Id is ABSENT from the modern response."""
    base_url, _ = live_server
    _, _, headers = _modern_request(base_url, method="server/discover", params={})
    for h, _ in headers.items():
        assert "session-id" not in h.lower(), h


def test_mcp_modern_missing_protocol_metadata_rejected(live_server: tuple[str, int]) -> None:
    """MCP MODERN E: request missing required _meta protocolVersion is rejected."""
    base_url, _ = live_server
    import json as _json
    from urllib import request as _r
    from urllib.error import HTTPError

    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {"_meta": {}},
    }
    req = _r.Request(
        f"{base_url}/mcp-mount/mcp",
        data=_json.dumps(body).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": MCP_MODERN_VERSION,
            "Mcp-Method": "tools/list",
        },
    )
    try:
        with _r.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
    except HTTPError as exc:
        # The SDK may surface a 400 (or stream an SSE error). Accept
        # both forms: the request MUST be rejected deterministically.
        assert exc.code in (400, 406, 415), exc.code
        return
    payload = _json.loads(raw) if raw else {}
    assert "error" in payload, payload
    assert payload["error"]["code"] == -32602, payload


def test_mcp_modern_unsupported_version_rejected(live_server: tuple[str, int]) -> None:
    """MCP MODERN F: unsupported / downgraded version is rejected."""
    base_url, _ = live_server
    import json as _json
    from urllib import request as _r
    from urllib.error import HTTPError

    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "server/discover",
        "params": {
            "_meta": {
                "io.modelcontextprotocol/protocolVersion": "2025-99-99",
                "io.modelcontextprotocol/clientCapabilities": {},
            }
        },
    }
    req = _r.Request(
        f"{base_url}/mcp-mount/mcp",
        data=_json.dumps(body).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": "2025-99-99",
            "Mcp-Method": "server/discover",
        },
    )
    try:
        with _r.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
    except HTTPError as exc:
        # Unsupported version may be surfaced as 400. The contract is
        # that the request is rejected; either HTTP-level or
        # JSON-RPC-level rejection is acceptable.
        assert exc.code in (400, 406, 415), exc.code
        return
    payload = _json.loads(raw) if raw else {}
    assert "error" in payload, payload
    assert payload["error"]["code"] == -32022, payload
    assert payload["error"]["data"]["supported"] == ["2026-07-28"]


def test_positive_phase4_chain_to_razorguard_allow(live_server: tuple[str, int]) -> None:
    """Positive: MCP MODERN -> UCP -> AP2 -> Firewall -> IR -> MATCH -> ALLOW."""
    base_url, _ = live_server
    intent_id = _create_fixture_intent(base_url)
    product_id = _catalog_product(base_url)
    result = _modern_call_tool(
        base_url,
        "complete_authorized_checkout",
        {
            "intent_id": intent_id,
            "product_id": product_id,
            "quantity": 1,
        },
    )
    assert result["decision"] == "ALLOW", result
    assert result["mcp_version"] == "2026-07-28"
    assert result["ucp_version"] == "2026-04-08"
    assert result["ap2_version"] == "v0.2.0"
    assert result["firewall"] == "PROTOCOL_PASS"
    assert result["cross_protocol_consistency"] == "MATCH"
    assert result["razorguard"] == "ALLOW"
    assert result["tickets_endpoint"] == "/buyer/execute"


def test_negative_material_mutation_blocks(live_server: tuple[str, int]) -> None:
    """Negative: mutated quantity that violates authorization is blocked."""
    base_url, _ = live_server
    intent_id = _create_fixture_intent(base_url)
    product_id = _catalog_product(base_url)
    result = _modern_call_tool(
        base_url,
        "complete_authorized_checkout",
        {
            "intent_id": intent_id,
            "product_id": product_id,
            "quantity": 7,  # > max_quantity=2 on the fixture intent
        },
    )
    assert result["decision"] == "BLOCK", result


def test_replay_same_request_no_duplicate_authority(live_server: tuple[str, int]) -> None:
    """Replay: identical request with same idempotency_key is consistent."""
    base_url, _ = live_server
    intent_id = _create_fixture_intent(base_url)
    product_id = _catalog_product(base_url)
    idem = f"idem-replay-{int(time.time() * 1000)}"
    a = _modern_call_tool(
        base_url,
        "complete_authorized_checkout",
        {
            "intent_id": intent_id,
            "product_id": product_id,
            "quantity": 1,
            "idempotency_key": idem,
        },
    )
    b = _modern_call_tool(
        base_url,
        "complete_authorized_checkout",
        {
            "intent_id": intent_id,
            "product_id": product_id,
            "quantity": 1,
            "idempotency_key": idem,
        },
    )
    assert a["run_id"] == b.get("run_id") or b.get("decision") == "BLOCK", (a, b)


def test_conflict_same_idempotency_changed_payload(live_server: tuple[str, int]) -> None:
    """Conflict: same idempotency key with changed payload is rejected."""
    base_url, _ = live_server
    intent_id = _create_fixture_intent(base_url)
    product_id = _catalog_product(base_url)
    idem = f"idem-conflict-{int(time.time() * 1000)}"
    _modern_call_tool(
        base_url,
        "complete_authorized_checkout",
        {
            "intent_id": intent_id,
            "product_id": product_id,
            "quantity": 1,
            "idempotency_key": idem,
        },
    )
    # Different run_id + same idempotency key = replay/reject.
    b = _modern_call_tool(
        base_url,
        "complete_authorized_checkout",
        {
            "intent_id": intent_id,
            "product_id": product_id,
            "quantity": 1,
            "idempotency_key": idem,
            "run_id": "acc-different-run",
        },
    )
    assert b["decision"] == "BLOCK", b
    assert "replay" in (b.get("reason") or "").lower(), b


def test_concurrent_identical_complete_authorized_checkout_exactly_one_effect(
    live_server: tuple[str, int],
) -> None:
    """MCP MODERN G + concurrency: 20 identical modern calls → exactly one provider effect.

    We exercise the concurrency proof via the production HTTP path
    ``POST /phase4/acceptance/prepare`` which is what the MCP modern
    ``complete_authorized_checkout`` tool delegates to. The MCP
    Streamable HTTP transport serialises through a single task group
    and is not a true parallel ingress; the production-scale
    concurrency proof lives in ``concurrency_proof.py`` (30/50/40/50
    worker storms across AP2/MCP/UCP/ACP) and is covered by
    ``test_concurrency_proof.py``.

    This test proves the same exactly-once invariant at the HTTP
    acceptance ingress: under 20 concurrent identical requests with
    the same idempotency_key, the system must authorise exactly ONE
    business/provider effect. All other calls must report the SAME
    run_id (idempotent re-read) or be rejected (replay).
    """
    import concurrent.futures as _cf
    import json as _json
    from urllib import request as _r

    base_url, _ = live_server
    intent_id = _create_fixture_intent(base_url)
    product_id = _catalog_product(base_url)
    idem = f"idem-conc-{int(time.time() * 1000)}"
    body = _json.dumps(
        {
            "intent_id": intent_id,
            "product_id": product_id,
            "quantity": 1,
            "idempotency_key": idem,
        }
    ).encode("utf-8")

    def _one_call() -> dict[str, Any]:
        import time as _t

        for _attempt in range(5):
            try:
                req = _r.Request(
                    f"{base_url}/phase4/acceptance/prepare",
                    data=body,
                    method="POST",
                    headers={"Content-Type": "application/json"},
                )
                with _r.urlopen(req, timeout=60) as resp:
                    text = resp.read().decode("utf-8")
                return {"_status": 200, **(_json.loads(text) if text else {})}
            except _r.HTTPError as exc:
                # 409 is the documented "replay/reject" response.
                if exc.code == 409:
                    try:
                        body_text = exc.read().decode("utf-8")
                        return {"_status": 409, **(_json.loads(body_text) if body_text else {})}
                    except Exception:
                        return {"_status": 409, "_detail": "conflict"}
                if _attempt == 4:
                    return {"_error": repr(exc)}
                _t.sleep(0.05 * (_attempt + 1))
            except Exception as exc:
                if _attempt == 4:
                    return {"_error": repr(exc)}
                _t.sleep(0.05 * (_attempt + 1))
        return {"_error": "exhausted"}

    with _cf.ThreadPoolExecutor(max_workers=20) as ex:
        results = list(ex.map(lambda _: _one_call(), range(20)))

    # Every response must be 200 (consumed) or 409 (replay/reject).
    statuses = {r.get("_status") for r in results}
    assert statuses <= {200, 409}, results
    assert "_error" not in {k for r in results for k in r}, results
    # At most one run_id may appear across all successful (200) responses.
    run_ids = {r["run_id"] for r in results if r.get("_status") == 200 and "run_id" in r}
    assert len(run_ids) <= 1, results
    # The registry must show exactly one run for this idempotency key.
    registry = _http_get_json(f"{base_url}/phase4/acceptance/runs")
    matching = [r for r in registry.get("runs", []) if r.get("idempotency_key") == idem]
    assert len(matching) == 1, matching
    # And the matching run must be the one every successful response
    # reported.
    if run_ids:
        assert run_ids.pop() == matching[0]["run_id"]
