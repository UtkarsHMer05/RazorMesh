"""F012 + S003: DEMO PREFLIGHT — authoritative presenter readiness.

S003 contract:
- the Razorpay lane runs the REAL validate_payment_provider_config; incomplete
  config → NOT READY (never a blanket green);
- the AI Intent Compiler distinguishes CONFIGURED from LIVE REACHABLE — a
  requested warm-up that fails is NOT READY;
- the optional v2 challenger NEVER gates the required systems;
- the Ed25519 pair is labeled ExecutionTicket signing keys + a separate
  Protocol crypto capability line;
- the audit probe verifies the global chain;
- no secrets in the response; honest not-ready; warm-up non-authoritative.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from conftest import wipe_business_tables
from razormesh_api.api.main import app
from razormesh_api.catalog import seed_catalog
from razormesh_api.persistence.db import create_session_factory
from razormesh_api.persistence.repositories import Repositories
from razormesh_api.preflight import run_preflight
from razormesh_api.settings import Settings


@pytest.fixture()
def client(settings):  # type: ignore[no-untyped-def]
    import razormesh_api.api.main as api_main

    api_main.get_settings.cache_clear()
    app.dependency_overrides[api_main.get_settings] = lambda: settings
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _fresh_repos(settings: Settings) -> Repositories:  # type: ignore[no-untyped-def]
    engine = create_engine(settings.database_url, future=True)
    repos = Repositories(create_session_factory(engine))
    wipe_business_tables(engine)
    seed_catalog(repos)
    return repos


def test_preflight_authoritative_component_list() -> None:
    """S003 component set: required systems + optional challenger, with the
    renamed key line and the new protocol-crypto capability line."""
    report = run_preflight()
    names = [c["component"] for c in report["checks"]]
    assert names == [
        "PostgreSQL",
        "Redis",
        "Payment environment",
        "AI Intent Compiler",
        "Active Semantic Model",
        "ExecutionTicket signing keys",
        "Protocol crypto",
        "Audit chain",
        "V2 Challenger Shadow",
    ]
    by_name = {c["component"]: c for c in report["checks"]}
    # Real probes pass in this environment.
    for required_name in (
        "PostgreSQL",
        "Redis",
        "Active Semantic Model",
        "ExecutionTicket signing keys",
        "Protocol crypto",
        "Audit chain",
    ):
        assert by_name[required_name]["ready"] is True, required_name
        assert by_name[required_name]["required"] is True
    # The challenger is OPTIONAL — never gates the required systems.
    assert by_name["V2 Challenger Shadow"]["required"] is False
    # The crypto line states the real per-protocol capability.
    crypto_detail = by_name["Protocol crypto"]["detail"]
    assert "UCP RFC 9421" in crypto_detail and "AP2 ES256" in crypto_detail
    assert "binding evidence only" in crypto_detail


def test_required_vs_optional_states() -> None:
    """S003 states: REQUIRED SYSTEMS READY vs NOT READY — FIX BEFORE
    RECORDING; optional unavailability is disclosed without failing the gate."""
    report = run_preflight()
    assert report["required_systems_ready"] is True
    assert report["state"] == "REQUIRED SYSTEMS READY"
    assert isinstance(report["optional_unavailable"], list)


class _SecretStub:
    """Minimal SecretStr-shaped value for Settings stubs."""

    def __init__(self, v: str) -> None:
        self._v = v

    def get_secret_value(self) -> str:
        return self._v


def test_razorpay_mode_runs_real_config_validator(monkeypatch: pytest.MonkeyPatch) -> None:
    """RAZORPAY mode: incomplete provider config → NOT READY, never green."""
    from razormesh_api import preflight as preflight_module
    from razormesh_api.settings import get_settings

    incomplete = Settings(
        _env_file=None,
        payment_provider="razorpay",
        razorpay_key_id="",
        razorpay_key_secret="",
        razorpay_webhook_secret="",
    )
    monkeypatch.setattr(preflight_module, "get_settings", lambda: incomplete)
    probe = preflight_module._probe_payment_provider()
    assert probe["ready"] is False
    assert probe["required"] is True
    assert "NOT READY" in probe["detail"]
    assert "RAZORPAY" in probe["environment"]
    # the real validator's problem message surfaces (env var NAME only)
    assert "RAZORPAY_KEY_ID is required" in probe["detail"]
    get_settings.cache_clear()


def test_razorpay_mode_valid_config_is_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    from razormesh_api import preflight as preflight_module

    valid = Settings(
        _env_file=None,
        payment_provider="razorpay",
        razorpay_key_id="rzp_test_validshape000",
        razorpay_key_secret="valid-secret",
        razorpay_webhook_secret="valid-webhook-secret",
    )
    monkeypatch.setattr(preflight_module, "get_settings", lambda: valid)
    probe = preflight_module._probe_payment_provider()
    assert probe["ready"] is True
    assert probe["environment"] == "RAZORPAY TEST MODE"
    assert "provider config validated" in probe["detail"]


def test_mock_provider_is_ready(client: TestClient) -> None:
    """MOCK mode needs no credentials and is marked correctly."""
    res = client.get("/mission-control/preflight")
    payment = next(c for c in res.json()["checks"] if c["component"] == "Payment environment")
    assert payment["ready"] is True
    assert payment["environment"] == "LOCAL / MOCK"


def test_compiler_configured_vs_live_reachable(monkeypatch: pytest.MonkeyPatch) -> None:
    """S003: CONFIGURED (not probed) vs LIVE REACHABLE vs NOT READY on a
    failed live warm-up — never 'ready because credentials exist'."""
    from razormesh_api import preflight as preflight_module

    class Configured:
        tokenrouter_credentials_present = True

    monkeypatch.setattr(preflight_module, "get_settings", lambda: Configured())
    # warm_up=False → CONFIGURED / NOT PROBED (honest, still ready=True)
    probe = preflight_module._probe_intent_compiler(warm_up=False)
    assert probe["ready"] is True
    assert "CONFIGURED / NOT PROBED" in probe["detail"]

    # warm_up=True with a FAILING live probe → NOT READY
    import razormesh_api.intent_compiler as ic

    def broken_client(settings=None):  # type: ignore[no-untyped-def]
        raise RuntimeError("network down")

    monkeypatch.setattr(ic, "build_tokenrouter_client", broken_client)
    probe2 = preflight_module._probe_intent_compiler(warm_up=True)
    assert probe2["ready"] is False
    assert "NOT LIVE REACHABLE" in probe2["detail"]

    # credentials absent → NOT configured (required for the demo)
    class Unconfigured:
        tokenrouter_credentials_present = False

    monkeypatch.setattr(preflight_module, "get_settings", lambda: Unconfigured())
    probe3 = preflight_module._probe_intent_compiler(warm_up=False)
    assert probe3["ready"] is False
    assert "not configured" in probe3["detail"]


def test_optional_challenger_never_gates(monkeypatch: pytest.MonkeyPatch) -> None:
    """The v2 shadow unavailable → REQUIRED SYSTEMS still READY; disclosed as
    OPTIONAL DEMO CAPABILITY UNAVAILABLE."""
    import razormesh_api.challenger_shadow as cs
    from razormesh_api import preflight as preflight_module

    class UnavailableShadow:
        available = False
        reason = "FileNotFoundError: artifact absent"
        _artifact_hash = ""
        _candidate = ""

    # the probe imports get_challenger_shadow from its module inside the
    # function — patch the SOURCE module's attribute (lazy import resolves it
    # at call time from razormesh_api.challenger_shadow).
    monkeypatch.setattr(cs, "get_challenger_shadow", lambda: UnavailableShadow())
    report = run_preflight()
    assert report["required_systems_ready"] is True
    assert "V2 Challenger Shadow" in report["optional_unavailable"]
    assert report["state"] == (
        "REQUIRED SYSTEMS READY — OPTIONAL DEMO CAPABILITY UNAVAILABLE: V2 Challenger Shadow"
    )
    assert callable(preflight_module.run_preflight)


def test_failed_required_system_is_not_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    """A failing REQUIRED probe → NOT READY — FIX BEFORE RECORDING (no blanket
    green even when every other probe passes)."""
    from razormesh_api import preflight as preflight_module

    def broken_redis() -> dict[str, object]:
        return {"component": "Redis", "ready": False, "detail": "ConnectionError", "required": True}

    monkeypatch.setattr(preflight_module, "_probe_redis", broken_redis)
    report = run_preflight()
    assert report["required_systems_ready"] is False
    assert report["state"] == "NOT READY — FIX BEFORE RECORDING"


def test_audit_chain_actually_verified(settings: Settings) -> None:
    """The audit probe runs the REAL global ledger verify."""
    _fresh_repos(settings)
    report = run_preflight()
    audit = next(c for c in report["checks"] if c["component"] == "Audit chain")
    assert audit["ready"] is True
    assert "global hash chain verified valid over" in audit["detail"]


def test_warm_up_performs_non_authoritative_health_request() -> None:
    """warm_up=True performs the provider list-models health request only —
    never claims a compiled mandate."""
    report = run_preflight(warm_up_compiler=True)
    compiler = next(c for c in report["checks"] if c["component"] == "AI Intent Compiler")
    assert compiler["ready"] is True
    assert "LIVE REACHABLE" in compiler["detail"] or "CONFIGURED" in compiler["detail"]


def test_no_secrets_in_preflight_response(client: TestClient) -> None:
    res = client.get("/mission-control/preflight")
    blob = res.text
    for banned in ("sk-", "rzp_test_", "razormesh_local_dev", "SECRET"):
        assert banned not in blob, banned
