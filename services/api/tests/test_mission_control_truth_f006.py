"""F006: ONE user action → ONE mission lineage (single intent/checkout/trace).

Proves the deep-engine truth the video depends on:
- a mission run creates exactly ONE intent and ONE trace (no orphan
  preliminary intent/checkout from a silently-minted second mission);
- the protocol-thesis mission (the historical double-intent path: it used to
  delegate to the Scenario-B/C endpoints, which mint their OWN intent) now
  runs the SAME acceptance orchestrator on the mission's OWN intent;
- Scenario-B/C endpoints remain as compatibility wrappers (Phase-4 acceptance
  unchanged) while the mission engine never mints their intents;
- the same trace id is visible across surfaces for a single mission.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select

from conftest import wipe_business_tables
from razormesh_api.api.main import app
from razormesh_api.catalog import seed_catalog
from razormesh_api.persistence.db import create_session_factory
from razormesh_api.persistence.models import IntentContract
from razormesh_api.persistence.repositories import Repositories
from razormesh_api.security_missions import _RECIPES, run_mission


@pytest.fixture()
def repos(settings):  # type: ignore[no-untyped-def]
    engine = create_engine(settings.database_url, future=True)
    r = Repositories(create_session_factory(engine))
    wipe_business_tables(engine)
    seed_catalog(r)
    yield r
    wipe_business_tables(engine)


@pytest.fixture()
def client(settings):  # type: ignore[no-untyped-def]
    import razormesh_api.api.main as api_main

    api_main.get_settings.cache_clear()
    app.dependency_overrides[api_main.get_settings] = lambda: settings
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _intent_total(repos: Repositories) -> int:
    with repos.transaction() as session:
        return int(session.scalar(select(func.count()).select_from(IntentContract)))


def test_protocol_thesis_is_one_lineage(repos: Repositories) -> None:
    """The historical double-intent path is gone: the acceptance pipeline runs
    on the mission's OWN intent, with real scenario-C semantics (protocol
    PASS, RazorGuard BLOCK on the violated budget)."""
    before = _intent_total(repos)
    result = run_mission(repos, mission_id="protocol-thesis")
    after = _intent_total(repos)
    # ONE run minted exactly ONE intent — never a second mission lineage.
    assert after - before == 1, f"minted {after - before} intents"
    assert result["intent_id"]
    assert result["trace_id"]
    assert result["final_decision"] == "BLOCK"
    assert result["ticket_issued"] is False
    assert result["provider_contacted"] is False
    stages = {s["stage"]: s["status"] for s in result["stages"]}
    assert stages["protocol"] == "PROTOCOL_PASS"
    assert stages["razorguard"] == "BLOCK"
    assert stages["semantic"] == "BLOCK"
    assert stages["ticket"] == "WITHHELD"
    assert stages["provider"] == "NOT CONTACTED"


def test_every_primary_mission_is_single_lineage(repos: Repositories) -> None:
    """Safe + the four merchant attacks + protocol thesis each mint exactly
    one intent and report one trace — the ONE TRANSACTION / ONE
    AUTHORIZATION LINEAGE / ONE TRACE contract."""
    for mission_id in (
        "safe",
        "price-drift",
        "hidden-recurring",
        "quantity-increase",
        "merchant-swap",
        "protocol-thesis",
    ):
        before = _intent_total(repos)
        result = run_mission(repos, mission_id=mission_id)
        after = _intent_total(repos)
        assert after - before == 1, f"{mission_id} minted {after - before} intents"
        assert result["trace_id"], f"{mission_id} has no trace"


def test_scenario_endpoints_remain_compatibility_wrappers(client: TestClient) -> None:
    """Phase-4 acceptance scenario B/C endpoints keep working unchanged
    (their own fresh intents are THEIR documented contract — the mission
    engine simply never delegates to them anymore)."""
    r1 = client.post("/phase4/acceptance/demo/scenario-b-semantic-violation")
    assert r1.status_code == 200
    assert r1.json()["final_decision"] == "BLOCK"
    r2 = client.post("/phase4/acceptance/demo/scenario-c-protocol-valid-intent-invalid")
    assert r2.status_code == 200
    assert r2.json()["final_decision"] == "BLOCK"


def test_same_trace_across_surfaces(client: TestClient, repos: Repositories) -> None:
    """One mission → the SAME trace id resolves on the forensics and
    mission-control surfaces (the single-lineage cross-surface contract)."""
    res = client.post("/security-missions/protocol-thesis/run", json={})
    assert res.status_code == 200
    body: dict[str, Any] = res.json()
    trace_id = body["trace_id"]
    fr = client.get(f"/forensics/trace/{trace_id}")
    assert fr.status_code == 200
    assert fr.json()["trace"]["trace_id"] == trace_id
    mr = client.get(f"/mission-control/current-transaction/{trace_id}")
    assert mr.status_code == 200
    assert mr.json()["trace_id"] == trace_id
    assert mr.json()["intent_id"] == body["intent_id"]


def test_recipes_carry_their_own_intent_profile() -> None:
    """F006/G018: scenario semantics live in the mission's SINGLE intent via
    recipe data — the protocol-thesis intent caps the budget at ₹3,000 (the
    authorization the protocol-valid 2 x ₹2,499 packet violates)."""
    thesis = _RECIPES["protocol-thesis"]
    assert thesis.pipeline == "acceptance"
    assert thesis.intent_max_total_minor == 300_000
    assert thesis.intent_max_quantity == 2
    assert _RECIPES["safe"].pipeline == "razorguard"
