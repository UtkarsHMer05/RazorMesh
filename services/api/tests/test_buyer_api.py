"""M45 acceptance: buyer API flow + direct-bypass protection."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select

from razormesh_api.catalog import seed_catalog
from razormesh_api.persistence import models  # noqa: F401
from razormesh_api.persistence.db import create_session_factory
from razormesh_api.persistence.models import (
    AuthorizationSpend,
    Checkout,
    ExecutionAttempt,
)
from razormesh_api.persistence.repositories import Repositories
from razormesh_api.settings import Settings


@pytest.fixture()
def buyer_client(settings: Settings) -> Iterator[TestClient]:
    from conftest import wipe_business_tables
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


def _fixture_intent(client: TestClient) -> str:
    res = client.post("/buyer/fixture-intent")
    assert res.status_code == 200
    return res.json()["intent_id"]


def _cheapest_product_id(client: TestClient) -> str:
    listing = client.get("/catalog/products", params={"limit": 100}).json()
    cheapest = min(listing["items"], key=lambda p: p["price_minor"])
    return cheapest["id"]


def test_full_buyer_flow_propose_allow_and_execute(buyer_client: TestClient) -> None:
    intent_id = _fixture_intent(buyer_client)
    product_id = _cheapest_product_id(buyer_client)

    res = buyer_client.post(
        "/buyer/propose",
        json={"intent_id": intent_id, "items": [{"product_id": product_id, "quantity": 1}]},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["decision"] == "ALLOW"
    assert body["ticket_json"] is not None

    run = buyer_client.post(
        "/buyer/execute",
        json={
            "intent_id": intent_id,
            "checkout_id": body["checkout_id"],
            "ticket_json": body["ticket_json"],
            "signature_hex": body["signature_hex"],
        },
    )
    assert run.status_code == 200, run.text
    assert run.json()["state"] == "SUCCEEDED"


def test_client_total_manipulation_rejected_via_api(buyer_client: TestClient) -> None:
    intent_id = _fixture_intent(buyer_client)
    # unknown product id (valid ULID shape) is the API-reachable manipulation probe
    res = buyer_client.post(
        "/buyer/propose",
        json={
            "intent_id": intent_id,
            "items": [{"product_id": "prd_01ARZ3NDEKTSV4RRFFQ69G5FAV", "quantity": 1}],
        },
    )
    assert res.status_code == 422


def test_execution_without_ticket_rejected(buyer_client: TestClient) -> None:
    intent_id = _fixture_intent(buyer_client)
    res = buyer_client.post(
        "/buyer/execute",
        json={
            "intent_id": intent_id,
            "checkout_id": "chk_01ARZ3NDEKTSV4RRFFQ69G5FAV",
            "ticket_json": '{"schema":"razormesh.ticket.v1","forged":true}',
            "signature_hex": "00" * 32,
        },
    )
    assert res.status_code in (403, 404)  # fail-closed either way


def test_blocked_intent_cannot_propose_via_api(buyer_client: TestClient) -> None:
    intent_id = _fixture_intent(buyer_client)
    engine = create_engine(_db_url(), future=True)
    from sqlalchemy import text as sql

    with engine.begin() as conn:
        conn.execute(
            sql("UPDATE intent_contracts SET status='BLOCKED' WHERE intent_id=:i").bindparams(
                i=intent_id
            )
        )
    product_id = _cheapest_product_id(buyer_client)
    res = buyer_client.post(
        "/buyer/propose",
        json={"intent_id": intent_id, "items": [{"product_id": product_id}]},
    )
    assert res.status_code == 422


def _db_url() -> str:
    from razormesh_api.settings import get_settings

    return get_settings().database_url


def test_proposal_persists_durable_checkout_row(buyer_client: TestClient) -> None:
    intent_id = _fixture_intent(buyer_client)
    product_id = _cheapest_product_id(buyer_client)
    res = buyer_client.post(
        "/buyer/propose",
        json={"intent_id": intent_id, "items": [{"product_id": product_id, "quantity": 2}]},
    )
    body = res.json()
    engine = create_engine(_db_url(), future=True)
    repos = Repositories(create_session_factory(engine))
    with repos.transaction() as s:
        row = s.get(Checkout, body["checkout_id"])
    assert row is not None
    assert row.computed_total_minor == body["total_minor"]


def test_forged_ticket_cannot_reserve_authorization_capacity(buyer_client: TestClient) -> None:
    intent_id = _fixture_intent(buyer_client)
    product_id = _cheapest_product_id(buyer_client)
    proposal = buyer_client.post(
        "/buyer/propose",
        json={"intent_id": intent_id, "items": [{"product_id": product_id}]},
    ).json()
    forged = buyer_client.post(
        "/buyer/execute",
        json={
            "intent_id": intent_id,
            "checkout_id": proposal["checkout_id"],
            "ticket_json": proposal["ticket_json"],
            "signature_hex": "00" * 64,
        },
    )
    assert forged.status_code == 403

    engine = create_engine(_db_url(), future=True)
    with create_session_factory(engine)() as session:
        spend = session.get(AuthorizationSpend, intent_id)
        attempts = session.execute(select(ExecutionAttempt)).scalars().all()
    assert spend is not None
    assert spend.reserved_minor == 0 and spend.committed_minor == 0
    assert attempts == []


def test_replay_does_not_leak_a_second_reservation(buyer_client: TestClient) -> None:
    intent_id = _fixture_intent(buyer_client)
    product_id = _cheapest_product_id(buyer_client)
    proposal = buyer_client.post(
        "/buyer/propose",
        json={"intent_id": intent_id, "items": [{"product_id": product_id}]},
    ).json()
    request = {
        "intent_id": intent_id,
        "checkout_id": proposal["checkout_id"],
        "ticket_json": proposal["ticket_json"],
        "signature_hex": proposal["signature_hex"],
    }
    assert buyer_client.post("/buyer/execute", json=request).status_code == 200
    assert buyer_client.post("/buyer/execute", json=request).status_code == 200

    engine = create_engine(_db_url(), future=True)
    with create_session_factory(engine)() as session:
        spend = session.get(AuthorizationSpend, intent_id)
        attempts = session.execute(select(ExecutionAttempt)).scalars().all()
    assert spend is not None
    assert spend.reserved_minor == 0
    assert spend.committed_minor == proposal["total_minor"]
    assert len(attempts) == 1
