"""M47 acceptance: audit dashboard API — timeline, verify, state, tamper test."""


import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from razormesh_api.catalog import seed_catalog
from razormesh_api.persistence.db import create_session_factory
from razormesh_api.persistence.repositories import Repositories


@pytest.fixture()
def audit_client(settings):  # type: ignore[no-untyped-def]
    from conftest import wipe_business_tables
    from razormesh_api import api

    api.main.get_settings.cache_clear()
    app = api.main.app
    app.dependency_overrides[api.main.get_settings] = lambda: settings
    engine = create_engine(settings.database_url, future=True)
    repos = Repositories(create_session_factory(engine))
    wipe_business_tables(engine)
    seed_catalog(repos)
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    wipe_business_tables(engine)


def _make_intent(client: TestClient) -> str:
    return client.post("/buyer/fixture-intent").json()["intent_id"]


def test_timeline_lists_events_chronologically(audit_client: TestClient) -> None:
    iid = _make_intent(audit_client)
    product_id = _cheapest_product_id(audit_client)
    audit_client.post(
        "/buyer/propose",
        json={"intent_id": iid, "items": [{"product_id": product_id}]},
    )
    res = audit_client.get("/audit/timeline")
    assert res.status_code == 200
    events = res.json()["events"]
    seqs = [e["seq"] for e in events]
    assert seqs == sorted(seqs)
    assert any(e["event_type"] == "CHECKOUT_PROPOSED" for e in events)
    assert all(len(e["current_event_hash_head"]) == 16 for e in events)


def _cheapest_product_id(client: TestClient) -> str:
    listing = client.get("/catalog/products", params={"limit": 100}).json()
    return min(listing["items"], key=lambda p: p["price_minor"])["id"]


def test_verify_reports_valid_chain(audit_client: TestClient) -> None:
    iid = _make_intent(audit_client)
    audit_client.post(
        "/buyer/propose",
        json={
            "intent_id": iid,
            "items": [{"product_id": _cheapest_product_id(audit_client)}],
        },
    )
    body = audit_client.get("/audit/verify").json()
    assert body["valid"] is True
    assert body["events_checked"] >= 1


def test_state_endpoint_returns_spend_and_decisions(audit_client: TestClient) -> None:
    iid = _make_intent(audit_client)
    audit_client.post(
        "/buyer/propose",
        json={
            "intent_id": iid,
            "items": [{"product_id": _cheapest_product_id(audit_client)}],
        },
    )
    res = audit_client.get(f"/audit/state/{iid}")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "AUTHORIZED"
    # spend row exists only after execution; before that it is legitimately None
    assert body["spend"] is None or body["spend"]["authorized_minor"] > 0
    assert isinstance(body["decisions"], list)


def test_tamper_test_detects_and_restores(audit_client: TestClient) -> None:
    iid = _make_intent(audit_client)
    audit_client.post(
        "/buyer/propose",
        json={
            "intent_id": iid,
            "items": [{"product_id": _cheapest_product_id(audit_client)}],
        },
    )
    res = audit_client.post("/audit/tamper-test")
    assert res.status_code == 200
    body = res.json()
    assert body["detected"] is True

    # state restored: chain verifies again afterwards (fresh events appended later)
    after = audit_client.get("/audit/verify").json()
    assert after["valid"] is True


def test_malformed_intent_id_rejected(audit_client: TestClient) -> None:
    res = audit_client.get("/audit/state/not-an-intent-id")
    assert res.status_code == 400
