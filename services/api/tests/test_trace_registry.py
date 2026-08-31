"""Phase-5 (M009/M010/M011) acceptance: live-trace registry, event projection, read API.

Covers create/read/link/unknown for the registry, deterministic ordering and
privacy safety of the projection, and the strict-validation read endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from razormesh_api.catalog import seed_catalog
from razormesh_api.persistence.db import create_session_factory
from razormesh_api.persistence.repositories import Repositories
from razormesh_api.trace_registry import TraceRegistry, project_events


@pytest.fixture()
def trace_client(settings):  # type: ignore[no-untyped-def]
    from conftest import wipe_business_tables
    from razormesh_api import api

    api.main.get_settings.cache_clear()
    app = api.main.app
    app.dependency_overrides[api.main.get_settings] = lambda: settings
    engine = create_engine(settings.database_url, future=True)
    repos = Repositories(create_session_factory(engine))
    wipe_business_tables(engine)
    seed_catalog(repos)
    from fastapi.testclient import TestClient as TC

    with TC(app) as c:
        yield c
    app.dependency_overrides.clear()
    wipe_business_tables(engine)


def _make_intent(client: TestClient) -> str:
    return client.post("/buyer/fixture-intent").json()["intent_id"]


def _propose_cheapest(client: TestClient, intent_id: str) -> dict:
    listing = client.get("/catalog/products", params={"limit": 100}).json()
    product_id = min(listing["items"], key=lambda p: p["price_minor"])["id"]
    return client.post(
        "/buyer/propose",
        json={"intent_id": intent_id, "items": [{"product_id": product_id}]},
    ).json()


# --- M009: registry create/read/link/unknown --------------------------------


def test_fixture_intent_mints_trace_and_survives_reload(trace_client: TestClient) -> None:
    intent_id = _make_intent(trace_client)
    by_intent = trace_client.get(f"/trace/by-intent/{intent_id}").json()
    assert by_intent["intent_id"] == intent_id
    trace_id = by_intent["trace_id"]
    assert trace_id.startswith("RM-") and len(trace_id) == 9

    # Read via display id; linkage must be idempotent and survive reload.
    read = trace_client.get(f"/trace/{trace_id}").json()
    assert read["trace"]["trace_id"] == trace_id
    again = trace_client.get(f"/trace/by-intent/{intent_id}").json()
    assert again["trace_id"] == trace_id  # same intent → same trace


def test_unknown_trace_is_clean_404(trace_client: TestClient) -> None:
    assert trace_client.get("/trace/RM-ZZZZZZ").status_code == 404
    # malformed ids are rejected as unknown, not 500
    assert trace_client.get("/trace/rm-lower1").status_code == 404
    assert trace_client.get("/trace/RM-999").status_code == 404
    assert trace_client.get("/trace/'; DROP TABLE demo_traces; --").status_code == 404


def test_registry_links_checkout_and_keeps_intent_binding(trace_client: TestClient) -> None:
    from razormesh_api.persistence.db import create_session_factory
    from razormesh_api.settings import get_settings

    repos = Repositories(create_session_factory(create_engine(get_settings().database_url)))
    intent_id = _make_intent(trace_client)
    decision = _propose_cheapest(trace_client, intent_id)
    registry = TraceRegistry(repos)
    trace = registry.by_intent(intent_id)
    assert trace is not None
    checkout_id = decision["checkout_id"]
    # Link a checkout id: must update the same row, never mint a second trace.
    registry.get_or_create_for_intent(intent_id, checkout_id=checkout_id)
    assert registry.by_intent(intent_id).checkout_id == checkout_id
    rows = repos.factory()
    from sqlalchemy import select

    from razormesh_api.persistence.models import DemoTrace

    count = rows.execute(select(DemoTrace).where(DemoTrace.intent_id == intent_id)).scalars().all()
    rows.close()
    assert len(count) == 1


# --- M010: projection determinism + safety ----------------------------------


def test_projection_is_seq_ordered_and_safe(trace_client: TestClient) -> None:
    intent_id = _make_intent(trace_client)
    _propose_cheapest(trace_client, intent_id)
    trace_id = trace_client.get(f"/trace/by-intent/{intent_id}").json()["trace_id"]
    read = trace_client.get(f"/trace/{trace_id}").json()
    events = read["events"]
    assert events, "a proposed checkout must project at least a decision event"
    seqs = [e["seq"] for e in events]
    assert seqs == sorted(seqs)
    for ev in events:
        assert ev["stage"] in {
            "human",
            "agent",  # search/checkout proposal (EVENT_VOCABULARY.md)
            "merchant",  # sandbox mutations (EVENT_VOCABULARY.md)
            "razorguard",
            "semantic",
            "fusion",
            "ticket",
            "protocol",
            "provider",
            "reconciliation",
            "audit",
            "replay",
        }
        # Privacy: no secret-ish keys may appear anywhere in projected payloads.
        blob = str(ev).lower()
        for banned in ("signature", "key_secret", "rzp_live", "private_key", "premise"):
            assert banned not in blob, f"projected event leaks {banned}"
    # The propose flow must surface the deterministic decision.
    kinds = [e["kind"] for e in events]
    assert any(k.startswith("decision.") for k in kinds)
    assert read["trace"]["final_decision"] in {"ALLOW", "CHALLENGE", "BLOCK"}
    # Provider boundary is evidence-derived, not assumed.
    assert read["trace"]["provider_contacted"] is False
    assert read["trace"]["provider_call_count"] == 0


def test_incremental_poll_returns_only_new_events(trace_client: TestClient) -> None:
    intent_id = _make_intent(trace_client)
    trace_id = trace_client.get(f"/trace/by-intent/{intent_id}").json()["trace_id"]
    first = trace_client.get(f"/trace/events/{trace_id}").json()
    assert first["count"] >= 0
    _propose_cheapest(trace_client, intent_id)
    last_seq = max((e["seq"] for e in first["events"]), default=0)
    second = trace_client.get(f"/trace/events/{trace_id}", params={"after_seq": last_seq}).json()
    assert all(e["seq"] > last_seq for e in second["events"])
    assert second["count"] > 0


# --- M011: recent traces endpoint -------------------------------------------


def test_recent_traces_bounded_and_summarized(trace_client: TestClient) -> None:
    for _ in range(3):
        _make_intent(trace_client)
    res = trace_client.get("/trace/recent", params={"limit": 2}).json()
    assert res["count"] == 2
    for item in res["traces"]:
        assert item["trace_id"].startswith("RM-")
        assert "state" in item
        assert "provider_call_count" in item


def test_by_intent_rejects_unknown_shape(trace_client: TestClient) -> None:
    assert trace_client.get("/trace/by-intent/intent_NOT_A_ULID_AT_ALL").status_code == 404
    res = trace_client.get("/trace/by-intent/intent_01M19X68VHHBGW00H2CFB13KFM")
    # Valid shape but absent row → 404 (never mints for a non-existent intent).
    assert res.status_code == 404


def test_direct_project_events_unknown_intent_is_empty() -> None:
    # Pure-function check: an unknown intent projects to no events (no fabrication).
    from razormesh_api.settings import get_settings

    repos = Repositories(create_session_factory(create_engine(get_settings().database_url)))
    assert project_events(repos, "intent_01M19X68VHHBGW00H2CFB13KFM") == []
