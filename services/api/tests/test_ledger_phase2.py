"""P2-M44: Phase-2 evidence ledger upgrade.

Safe provider evidence (callback verification, webhook ingestion, operator
reconciliation passes) must land in the tamper-evident hash chain:
- exactly-once semantics: duplicates/failures never grow the chain;
- payloads carry safe identifiers ONLY (no secrets, no raw bodies);
- the whole chain still verifies after mixed Phase-1/Phase-2 events.
"""

import hashlib
import hmac as hmac_mod
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from razormesh_api import api as api_pkg
from razormesh_api.api.routes import ops as ops_route
from razormesh_api.api.routes import webhooks as webhooks_route
from razormesh_api.executor import TrustedPaymentExecutor
from razormesh_api.keys import DevSigningKeys
from razormesh_api.ledger import EvidenceLedger
from razormesh_api.persistence.models import AuditEvent as LedgerRow
from razormesh_api.persistence.models import (
    AuthorizationSpend,
    Checkout,
    Decision,
    ExecutionAttempt,
    ExecutionTicket,
)
from razormesh_api.persistence.models import IntentContract as RowIntent
from razormesh_api.persistence.repositories import Repositories
from razormesh_api.providers.razorpay import RazorpayClient, RazorpayPaymentProvider
from razormesh_api.reconciliation import ReconciliationOutcome
from razormesh_api.reducer import ProviderStateReducer
from razormesh_api.settings import Settings, get_settings
from razormesh_api.spend import SpendManager
from test_callback_verification import SECRET, _PaidTransport, _signature
from test_executor import _make_ticket, _redis

WEBHOOK_SECRET = "whsec-m44-test-value"


# ---------------------------------------------------------------------------
# Shared environment (mirrors the M23 harness; secrets are TEST constants)
# ---------------------------------------------------------------------------


class _DbTransport(httpx.BaseTransport):
    """Answers order fetches with the REAL stored order id."""

    def __init__(self, status: str = "created") -> None:
        self.status = status

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        from razormesh_api.persistence.db import create_db_engine, create_session_factory

        repos = Repositories(create_session_factory(create_db_engine(get_settings().database_url)))
        with repos.transaction() as s:
            row = (
                s.query(ExecutionAttempt)
                .filter(ExecutionAttempt.razorpay_order_id.isnot(None))
                .order_by(ExecutionAttempt.created_at.desc())
                .first()
            )
            oid = row.razorpay_order_id if row else "order_m44"
        return httpx.Response(
            200,
            json={"id": oid, "status": self.status, "amount": 100000, "currency": "INR"},
        )


@pytest.fixture()
def m44_env(tmp_path):  # type: ignore[no-untyped-def]
    from sqlalchemy import create_engine

    from razormesh_api.persistence.db import create_session_factory

    engine = create_engine(get_settings().database_url, future=True)
    repos = Repositories(create_session_factory(engine))
    keys = DevSigningKeys(
        private_path=str(tmp_path / "p.pem"), public_path=str(tmp_path / "pub.pem")
    ).ensure()
    spend = SpendManager(repos)
    client = RazorpayClient(
        key_id="rzp_test_k",
        key_secret=SECRET,
        base_url=get_settings().razorpay_api_base_url,
        timeout_seconds=5,
        transport=_PaidTransport(status="created"),
    )
    executor = TrustedPaymentExecutor(
        repos=repos,
        keys=keys,
        nonces=_redis(),
        provider=RazorpayPaymentProvider(client),
        spend=spend,
    )
    yield repos, keys, spend, executor
    with repos.transaction() as s:
        s.query(ExecutionAttempt).delete()
        s.query(ExecutionTicket).delete()
        s.query(Decision).delete()
        s.query(Checkout).delete()
        s.query(AuthorizationSpend).delete()
        s.query(RowIntent).delete()


def _settings_override() -> Settings:
    return Settings(
        database_url=get_settings().database_url,
        redis_url=get_settings().redis_url,
        payment_provider="razorpay",
        razorpay_key_id="rzp_test_k",
        razorpay_key_secret=SECRET,
        razorpay_webhook_secret=WEBHOOK_SECRET,
        _env_file=None,
    )


@pytest.fixture()
def api_client(monkeypatch):  # type: ignore[no-untyped-def]
    """App client with razorpay settings + provider seam patched for callbacks."""
    from razormesh_api.api.routes import buyer as buyer_route

    def fake_provider(settings: Settings):  # type: ignore[no-untyped-def]
        client = RazorpayClient(
            key_id="rzp_test_k",
            key_secret=SECRET,
            base_url=get_settings().razorpay_api_base_url,
            timeout_seconds=5,
            transport=_PaidTransport(status="paid"),
        )
        return RazorpayPaymentProvider(client)

    monkeypatch.setattr(buyer_route, "_razorpay_provider", fake_provider)

    def _override() -> Settings:
        return _settings_override()

    api_pkg.main.get_settings.cache_clear()
    app = api_pkg.main.app
    app.dependency_overrides[api_pkg.main.get_settings] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    api_pkg.main.get_settings.cache_clear()


def _run_trusted_flow(m44_env):  # type: ignore[no-untyped-def]
    repos, keys, spend, executor = m44_env
    signed, binding, contract = _make_ticket(keys, repos)
    spend.ensure_authorization(contract.intent_id, authorized_minor=5_000_000)
    attempt = executor.execute(signed_ticket=signed, binding=binding, intent_id=contract.intent_id)
    assert attempt.razorpay_order_id is not None
    with repos.transaction() as s:
        row = s.get(ExecutionAttempt, attempt.execution_attempt_id)
        assert row is not None
        return attempt.execution_attempt_id, str(row.checkout_id), str(contract.intent_id)


def _count_events(repos, event_type: str, intent_id: str | None = None) -> int:  # type: ignore[no-untyped-def]
    with repos.transaction() as s:
        q = s.query(LedgerRow).filter(LedgerRow.event_type == event_type)
        if intent_id is not None:
            q = q.filter(LedgerRow.intent_id == intent_id)
        return int(q.count())


def _payloads(repos, event_type: str) -> list[str]:  # type: ignore[no-untyped-def]
    import json as _json

    with repos.transaction() as s:
        rows = s.query(LedgerRow).filter(LedgerRow.event_type == event_type).all()
        return [_json.dumps(r.metadata_json) for r in rows]


# ---------------------------------------------------------------------------
# Callback verification evidence
# ---------------------------------------------------------------------------


def test_callback_verified_appends_exactly_once(m44_env, api_client) -> None:  # type: ignore[no-untyped-def]
    repos, _keys, _spend, _executor = m44_env
    attempt_id, checkout_id, intent_id = _run_trusted_flow(m44_env)
    order_id = _order(repos, attempt_id)

    body = {
        "execution_attempt_id": attempt_id,
        "intent_id": intent_id,
        "checkout_id": checkout_id,
        "razorpay_payment_id": "pay_m44_cb",
        "razorpay_order_id": order_id,
        "razorpay_signature": _signature(order_id, "pay_m44_cb"),
    }
    assert api_client.post("/buyer/callback", json=body).status_code == 200
    assert api_client.post("/buyer/callback", json=body).status_code == 200

    assert _count_events(repos, "RAZORPAY_CALLBACK_VERIFIED", intent_id) == 1
    for payload in _payloads(repos, "RAZORPAY_CALLBACK_VERIFIED"):
        assert SECRET not in payload  # evidence carries identifiers, not secrets


def _order(repos, attempt_id: str) -> str:  # type: ignore[no-untyped-def]
    with repos.transaction() as s:
        row = s.get(ExecutionAttempt, attempt_id)
        assert row is not None and row.razorpay_order_id
        return str(row.razorpay_order_id)


def test_forged_callback_grows_nothing(m44_env, api_client) -> None:  # type: ignore[no-untyped-def]
    repos, _keys, _spend, _executor = m44_env
    attempt_id, checkout_id, intent_id = _run_trusted_flow(m44_env)
    order_id = _order(repos, attempt_id)
    before = _count_events(repos, "RAZORPAY_CALLBACK_VERIFIED", intent_id)

    good = _signature(order_id, "pay_forged")
    forged = ("0" if good[0] != "0" else "1") + good[1:]
    res = api_client.post(
        "/buyer/callback",
        json={
            "execution_attempt_id": attempt_id,
            "intent_id": intent_id,
            "checkout_id": checkout_id,
            "razorpay_payment_id": "pay_forged",
            "razorpay_order_id": order_id,
            "razorpay_signature": forged,
        },
    )
    assert res.status_code == 403
    assert _count_events(repos, "RAZORPAY_CALLBACK_VERIFIED", intent_id) == before


# ---------------------------------------------------------------------------
# Webhook ingestion evidence (winner-only)
# ---------------------------------------------------------------------------


@pytest.fixture()
def wh_client(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    """Webhook route over a REAL reducer on the dev DB with test secrets."""
    from sqlalchemy import create_engine

    from razormesh_api.persistence.db import create_session_factory

    engine = create_engine(get_settings().database_url, future=True)
    repos = Repositories(create_session_factory(engine))
    keys = DevSigningKeys(
        private_path=str(tmp_path / "p.pem"), public_path=str(tmp_path / "pub.pem")
    ).ensure()

    def real_reducer(settings: Settings):  # type: ignore[no-untyped-def]
        return ProviderStateReducer(
            repos=repos, keys=keys, nonces=_redis(), provider=None, spend=SpendManager(repos)
        )

    monkeypatch.setattr(webhooks_route, "_reducer", real_reducer)

    def _override() -> Settings:
        return _settings_override()

    api_pkg.main.get_settings.cache_clear()
    app = api_pkg.main.app
    app.dependency_overrides[api_pkg.main.get_settings] = _override
    with TestClient(app) as c:
        yield c, repos
    app.dependency_overrides.clear()
    api_pkg.main.get_settings.cache_clear()


def _sign(body: bytes, secret: str = WEBHOOK_SECRET) -> str:
    return hmac_mod.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_webhook_ingested_event_winner_only(m44_env, wh_client) -> None:  # type: ignore[no-untyped-def]
    client, repos = wh_client
    attempt_id, _checkout_id, intent_id = _run_trusted_flow(m44_env)
    order_id = _order(repos, attempt_id)

    body = (
        '{"event":"payment.captured","payload":{"payment":{"entity":'
        '{"id":"pay_m44_wh","order_id":"' + order_id + '","amount":100000,"currency":"INR"}}}}'
    ).encode()
    # Event ids are unique PER RUN: the durable inbox persists across pytest
    # sessions and would classify a repeated id as DUPLICATE by design.
    event_id = f"evt_m44_{uuid4().hex}"
    headers = {
        "Content-Type": "application/json",
        "X-Razorpay-Signature": _sign(body),
        "x-razorpay-event-id": event_id,
    }
    first = client.post("/api/v1/webhooks/razorpay", content=body, headers=headers)
    assert first.json()["processed"] is True

    dup = client.post("/api/v1/webhooks/razorpay", content=body, headers=headers)
    assert dup.json()["duplicate"] is True

    assert _count_events(repos, "RAZORPAY_WEBHOOK_INGESTED", intent_id) == 1
    for payload in _payloads(repos, "RAZORPAY_WEBHOOK_INGESTED"):
        assert WEBHOOK_SECRET not in payload
        assert "signature_verified" in payload

    forged_headers = dict(headers)
    forged_headers["x-razorpay-event-id"] = f"evt_m44_{uuid4().hex}"
    forged_headers["X-Razorpay-Signature"] = _sign(body, "attacker-secret")
    bad = client.post("/api/v1/webhooks/razorpay", content=body, headers=forged_headers)
    assert bad.status_code == 403
    assert _count_events(repos, "RAZORPAY_WEBHOOK_INGESTED", intent_id) == 1


# ---------------------------------------------------------------------------
# Operator reconciliation pass evidence
# ---------------------------------------------------------------------------


def test_reconciliation_run_recorded(m44_env, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    repos, _keys, _spend, _executor = m44_env
    attempt_id, _checkout_id, intent_id = _run_trusted_flow(m44_env)
    order_id = _order(repos, attempt_id)

    outcome = ReconciliationOutcome(
        attempt_id=attempt_id,
        intent_id=intent_id,
        order_id=order_id,
        attempt_state_before="PROVIDER_UNKNOWN",
        attempt_state_after="SUCCEEDED",
        reconcile_state_after="RESOLVED",
        provider_order_status="paid",
        order_discovered_and_claimed=True,
        settled_by_reconciliation=True,
        detail="capture evidence reduced through provider-state reducer",
    )

    class _Stub:
        def reconcile(self, aid: str, *, now=None):  # type: ignore[no-untyped-def]
            return outcome

    def _override() -> Settings:
        return _settings_override()

    monkeypatch.setattr(ops_route, "_service", lambda settings: _Stub())
    api_pkg.main.get_settings.cache_clear()
    app = api_pkg.main.app
    app.dependency_overrides[api_pkg.main.get_settings] = _override
    try:
        client = TestClient(app)
        ran = client.post(f"/ops/reconciliation/{attempt_id}")
        assert ran.status_code == 200
    finally:
        app.dependency_overrides.clear()
        api_pkg.main.get_settings.cache_clear()

    events = _payloads(repos, "RAZORPAY_RECONCILIATION_RUN")
    assert any(order_id in p and "RESOLVED" in p for p in events)


# ---------------------------------------------------------------------------
# Chain integrity across mixed Phase-1/Phase-2 evidence
# ---------------------------------------------------------------------------


def test_chain_verifies_after_phase2_evidence(m44_env, wh_client) -> None:  # type: ignore[no-untyped-def]
    repos, _keys, _spend, _executor = m44_env
    report = EvidenceLedger(repos).verify()
    assert report.valid
