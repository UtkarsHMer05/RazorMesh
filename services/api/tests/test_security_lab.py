"""M46 acceptance: security lab API executes the synthetic suite server-side."""


import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from razormesh_api.catalog import seed_catalog
from razormesh_api.persistence.db import create_session_factory
from razormesh_api.persistence.repositories import Repositories


@pytest.fixture()
def buyer_client(settings):  # type: ignore[no-untyped-def]
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


def test_scenarios_endpoint_lists_registry(client: TestClient) -> None:
    res = client.get("/security-lab/scenarios")
    assert res.status_code == 200
    body = res.json()
    assert body["count"] == 7
    assert "synthetic" in body["note"].lower()
    ids = [s["scenario_id"] for s in body["scenarios"]]
    assert len(set(ids)) == 7


def test_run_executes_all_synthetic_scenarios(buyer_client: TestClient) -> None:
    """Full suite runs through the real pipeline and reports honest outcomes."""
    res = buyer_client.post("/security-lab/run")
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 7
    assert body["passed"] == body["total"], [
        (r["scenario_id"], r["actual"]) for r in body["results"] if not r["passed"]
    ]
    # evidence tail is a hash-chained ledger excerpt
    tail = body["evidence_tail"]
    assert len(tail) > 0
    assert all("hash_head" in e and len(e["hash_head"]) == 16 for e in tail)
