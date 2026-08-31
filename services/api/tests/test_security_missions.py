"""Deep-engine correction (G016-G018) acceptance: security missions.

Proves:
- G016: every mission card runs THAT mission only. Clicking price-drift
  does NOT run the whole suite; the full suite is a separate endpoint.
- G017: the attack movie is event-driven — the mission result carries the
  trace's REAL projected events; a stage without a backend event is
  absent/pending, never a fabricated DONE.
- G018: Safe, hidden-recurring, price-drift, and protocol-thesis all run
  through the SAME mission orchestration (recipes are data; no
  per-mission business logic).
- Provider-zero: attack missions never contact the provider (audit-backed
  evidence; the demo runs the mock provider anyway).
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from conftest import wipe_business_tables
from razormesh_api.catalog import seed_catalog
from razormesh_api.persistence.db import create_session_factory
from razormesh_api.persistence.repositories import Repositories
from razormesh_api.security_missions import mission_catalog, run_mission

# The master-prompt required dedicated missions.
_REQUIRED_MISSIONS = {
    "price-drift",
    "hidden-recurring",
    "merchant-swap",
    "quantity-increase",
    "protocol-thesis",
    "safe",
}


@pytest.fixture()
def missions_client(settings):  # type: ignore[no-untyped-def]
    from razormesh_api import api

    api.main.get_settings.cache_clear()
    app = api.main.app
    app.dependency_overrides[api.main.get_settings] = lambda: settings
    engine = create_engine(settings.database_url, future=True)
    repos = Repositories(create_session_factory(engine))
    wipe_business_tables(engine)
    seed_catalog(repos)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    wipe_business_tables(engine)


def _run(client: TestClient, mission_id: str) -> dict[str, Any]:
    res = client.post(f"/security-missions/{mission_id}/run", json={})
    assert res.status_code == 200, (mission_id, res.text[:300])
    return res.json()


# ---------------------------------------------------------------------------
# G016 — dedicated missions
# ---------------------------------------------------------------------------


def test_catalog_covers_required_dedicated_missions() -> None:
    missions = {m["mission_id"] for m in mission_catalog()}
    assert _REQUIRED_MISSIONS <= missions


def test_price_drift_runs_only_price_drift(missions_client: TestClient) -> None:
    """Clicking Price Drift must NOT run the entire suite.

    Proven by output shape: a dedicated mission returns ONE mission result
    (one trace, one set of events) — never 22 scenario results.
    """
    body = _run(missions_client, "price-drift")
    # one mission, one trace, one event stream
    assert body["mission_id"] == "price-drift"
    assert "results" not in body, "a mission card must never return suite results"
    assert "scenario_id" not in body
    # the price-drift mutation really happened (G006-style real mutation)
    kinds = [m["kind"] for m in body["mutations_applied"]]
    assert kinds == ["price_drift"]
    # ...and the pipeline caught it
    assert body["final_decision"] == "BLOCK"
    assert body["ticket_issued"] is False
    assert body["provider_contacted"] is False


def test_full_suite_is_a_separate_endpoint(missions_client: TestClient) -> None:
    """The 22-scenario suite is its own explicit action (G016)."""
    res = missions_client.post("/security-missions/suite")
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 22
    assert len(body["results"]) == 22
    assert all("scenario_id" in r for r in body["results"])


@pytest.mark.parametrize(
    "mission_id",
    ["price-drift", "hidden-recurring", "merchant-swap", "quantity-increase"],
)
def test_each_attack_mission_blocks_and_never_contacts_provider(
    missions_client: TestClient, mission_id: str
) -> None:
    body = _run(missions_client, mission_id)
    assert body["final_decision"] == "BLOCK", mission_id
    assert body["ticket_issued"] is False
    assert body["provider_contacted"] is False
    # real mutation applied for this mission only
    assert len(body["mutations_applied"]) == 1


def test_unknown_mission_is_404(missions_client: TestClient) -> None:
    res = missions_client.post("/security-missions/gravito/run", json={})
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# G017 — event-driven movie
# ---------------------------------------------------------------------------


def test_movie_events_are_real_trace_events(missions_client: TestClient) -> None:
    """The mission's events come from the trace projection (audit-backed),
    and every event carries a real seq + stage."""
    body = _run(missions_client, "hidden-recurring")
    events = body["events"]
    assert events, "the mission must carry its trace events"
    seqs = [e["seq"] for e in events]
    assert seqs == sorted(seqs), "events are seq-ordered"
    stages = [e["stage"] for e in events]
    # the merchant mutation event is REAL (from the ledger projection)
    assert "merchant" in stages
    merchant_ev = next(e for e in events if e["stage"] == "merchant")
    assert merchant_ev["kind"] == "offer.mutated"
    # provider-contacted claims derive from provider events ONLY
    if body["provider_contacted"] is False:
        assert not any(e["stage"] == "provider" for e in events)


def test_absent_backend_event_is_never_fabricated_done(missions_client: TestClient) -> None:
    """A mission whose trace has no ticket event shows no fabricated
    ticket stage in the event list (G017 anti-hardcoding)."""
    body = _run(missions_client, "quantity-increase")
    stages = {e["stage"] for e in body["events"]}
    # BLOCK mission: no ticket was ever issued, so no ticket event exists
    assert "ticket" not in stages or all(e["kind"] != "ticket.issued" for e in body["events"])
    # the stages array carries only WITHHELD for blocked missions
    ticket_stage = next((s for s in body["stages"] if s["stage"] == "ticket"), None)
    if ticket_stage:
        assert ticket_stage["status"] == "WITHHELD"


def test_read_only_trace_replay(missions_client: TestClient) -> None:
    """The movie replay endpoint returns stored events only."""
    body = _run(missions_client, "price-drift")
    trace_id = body["trace_id"]
    res = missions_client.get(f"/security-missions/trace/{trace_id}/replay")
    assert res.status_code == 200
    replay = res.json()
    assert replay["read_only"] is True
    assert replay["trace_id"] == trace_id
    assert [e["seq"] for e in replay["events"]] == sorted(e["seq"] for e in replay["events"])
    # replay agrees with the run: same event count for the same trace
    assert len(replay["events"]) == len(body["events"])
    unknown = missions_client.get("/security-missions/trace/RM-ZZZZZZ/replay")
    assert unknown.status_code == 404


# ---------------------------------------------------------------------------
# G018 — one mission engine
# ---------------------------------------------------------------------------


def test_safe_hidden_recurring_price_drift_and_protocol_thesis_share_orchestration(
    missions_client: TestClient,
) -> None:
    """All four named missions run through the same primitive: each result
    carries the same orchestration fields, produced by run_mission()."""
    for mission_id in ("safe", "hidden-recurring", "price-drift", "protocol-thesis"):
        body = _run(missions_client, mission_id)
        # the shared orchestration contract (create->mutate->execute->observe)
        for field_name in (
            "mission_id",
            "trace_id",
            "intent_id",
            "checkout_id",
            "mutations_applied",
            "pipeline",
            "final_decision",
            "stages",
            "events",
        ):
            assert field_name in body, (mission_id, field_name)
    # the recipes genuinely differ in DATA (mutations/pipeline), not code paths
    safe = _run(missions_client, "safe")
    hidden = _run(missions_client, "hidden-recurring")
    thesis = _run(missions_client, "protocol-thesis")
    assert safe["mutations_applied"] == []
    assert [m["kind"] for m in hidden["mutations_applied"]] == ["hidden_membership"]
    assert thesis["pipeline"] == "acceptance"
    assert safe["pipeline"] == "razorguard"


def test_safe_mission_allows_without_provider_contact_in_demo(
    missions_client: TestClient,
) -> None:
    """The safe mission: the drift-free checkout passes revalidation (ALLOW)
    and the demo still never contacts the provider (no ticket minted by the
    demo mission engine — provider evidence stays audit-backed)."""
    body = _run(missions_client, "safe")
    assert body["final_decision"] == "ALLOW"
    assert body["provider_contacted"] is False
    assert body["attack"] is False


def test_mission_binds_to_current_trace_intent(missions_client: TestClient) -> None:
    """A mission run for the CURRENT mission intent resolves that trace."""
    first = _run(missions_client, "safe")
    res = missions_client.post(
        "/security-missions/price-drift/run",
        json={"intent_id": first["intent_id"]},
    )
    assert res.status_code == 200
    second = res.json()
    assert second["intent_id"] == first["intent_id"]
    assert second["trace_id"] == first["trace_id"]


def test_run_mission_engine_directly(missions_client: TestClient) -> None:
    """The orchestration is importable and shared (G018's one-engine proof)."""
    from razormesh_api.settings import get_settings

    settings = get_settings()
    engine = create_engine(settings.database_url, future=True)
    repos = Repositories(create_session_factory(engine))
    body = run_mission(repos, mission_id="condition-downgrade")
    assert body["mission_id"] == "condition-downgrade"
    assert body["final_decision"] == "BLOCK"
    assert [m["kind"] for m in body["mutations_applied"]] == ["condition_downgrade"]
