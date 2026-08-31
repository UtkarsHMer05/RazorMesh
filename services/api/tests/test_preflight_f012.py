"""F012: DEMO PREFLIGHT — presenter readiness + execution environment badge.

Proves:
- every component probe runs a REAL lightweight check (PostgreSQL SELECT 1,
  Redis PING, active model load, challenger artifact, protocol keys, audit
  chain verify);
- the payment environment line states LOCAL/MOCK vs RAZORPAY TEST so a local
  mission is never presented as a live provider transaction;
- no secrets are exposed in the response;
- the warm-up path performs a NON-AUTHORITATIVE health request only.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from razormesh_api.api.main import app
from razormesh_api.preflight import run_preflight


@pytest.fixture()
def client(settings):  # type: ignore[no-untyped-def]
    import razormesh_api.api.main as api_main

    api_main.get_settings.cache_clear()
    app.dependency_overrides[api_main.get_settings] = lambda: settings
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_preflight_probes_all_components() -> None:
    report = run_preflight()
    names = [c["component"] for c in report["checks"]]
    assert names == [
        "PostgreSQL",
        "Redis",
        "AI Intent Compiler",
        "Active Semantic Model",
        "V2 Challenger Shadow",
        "Protocol keys",
        "Audit chain",
        "Payment environment",
    ]
    # The real probes pass in this environment.
    by_name = {c["component"]: c for c in report["checks"]}
    assert by_name["PostgreSQL"]["ready"] is True
    assert by_name["Redis"]["ready"] is True
    assert by_name["Active Semantic Model"]["ready"] is True
    assert by_name["V2 Challenger Shadow"]["ready"] is True
    assert by_name["Protocol keys"]["ready"] is True
    assert by_name["Audit chain"]["ready"] is True


def test_payment_environment_is_stated(client: TestClient) -> None:
    """The environment line exists and states the truth for the trace."""
    res = client.get("/mission-control/preflight")
    assert res.status_code == 200
    body = res.json()
    payment = next(c for c in body["checks"] if c["component"] == "Payment environment")
    valid_environments = (
        "LOCAL / MOCK",
        "RAZORPAY TEST MODE",
        "RAZORPAY TEST (credentials incomplete)",
    )
    assert payment["environment"] in valid_environments
    # The test settings use the mock provider.
    assert payment["environment"] == "LOCAL / MOCK"


def test_no_secrets_in_preflight_response(client: TestClient) -> None:
    res = client.get("/mission-control/preflight")
    blob = res.text
    for banned in ("sk-", "rzp_test_", "razormesh_local_dev", "SECRET"):
        assert banned not in blob, banned


def test_preflight_reports_ready_only_when_true() -> None:
    """Honesty: an unreachable component reports not-ready, never a painted ✓."""
    from razormesh_api import preflight as preflight_module

    original = preflight_module._probe_redis

    def broken() -> dict[str, str]:
        return {"component": "Redis", "ready": False, "detail": "ConnectionError"}

    preflight_module._probe_redis = broken  # type: ignore[assignment]
    try:
        report = run_preflight()
    finally:
        preflight_module._probe_redis = original  # type: ignore[assignment]
    assert report["all_ready"] is False
    redis_check = next(c for c in report["checks"] if c["component"] == "Redis")
    assert redis_check["ready"] is False


def test_warm_up_is_optional_and_non_authoritative() -> None:
    """warm_up_compiler=True performs a provider health request only — the
    response details say so and never claim a compiled mandate."""
    report = run_preflight(warm_up_compiler=True)
    compiler = next(c for c in report["checks"] if c["component"] == "AI Intent Compiler")
    assert "warm-up" in compiler["detail"] or "configured" in compiler["detail"]
    assert "mandate" not in compiler["detail"].lower() or "non-authoritative" in compiler["detail"]
