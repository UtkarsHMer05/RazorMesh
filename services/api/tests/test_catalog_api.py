"""M23 acceptance: bounded read-only catalog API with validation + pagination."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from razormesh_api.catalog import seed_catalog
from razormesh_api.persistence import models  # noqa: F401
from razormesh_api.persistence.db import create_session_factory
from razormesh_api.persistence.repositories import Repositories
from razormesh_api.settings import Settings


@pytest.fixture()
def seeded_client(settings: Settings) -> Iterator[TestClient]:
    """Client with a freshly seeded catalog, wiped afterwards."""
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


def test_merchants_endpoint_paginates(seeded_client: TestClient) -> None:
    res = seeded_client.get("/catalog/merchants", params={"limit": 2, "offset": 0})
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 5
    assert body["limit"] == 2
    assert len(body["items"]) == 2
    page2 = seeded_client.get("/catalog/merchants", params={"limit": 3, "offset": 2})
    assert page2.status_code == 200
    assert len(page2.json()["items"]) == 3
    ids_page1 = {m["id"] for m in body["items"]}
    ids_page2 = {m["id"] for m in page2.json()["items"]}
    assert not (ids_page1 & ids_page2)


def test_products_endpoint_filters_and_validates(seeded_client: TestClient) -> None:
    res = seeded_client.get("/catalog/products", params={"category": "audio", "limit": 100})
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 10
    assert all(p["category"] == "audio" for p in body["items"])

    # pagination bounds enforced: limit=0 and limit>100 are rejected
    for bad in ({"limit": 0}, {"limit": 101}, {"offset": -1}):
        r = seeded_client.get("/catalog/products", params=bad)
        assert r.status_code == 422, bad

    # filter values are length-bounded
    r = seeded_client.get("/catalog/products", params={"category": "x" * 101})
    assert r.status_code == 422


def test_product_get_by_typed_id(seeded_client: TestClient) -> None:
    listing = seeded_client.get("/catalog/products", params={"limit": 1}).json()
    product_id = listing["items"][0]["id"]
    res = seeded_client.get(f"/catalog/products/{product_id}")
    assert res.status_code == 200
    assert res.json()["id"] == product_id


def test_product_rejects_malformed_id(seeded_client: TestClient) -> None:
    res = seeded_client.get("/catalog/products/prd_NOT_A_VALID_ULID")
    assert res.status_code == 422


def test_product_missing_returns_404(seeded_client: TestClient) -> None:
    res = seeded_client.get("/catalog/products/prd_01ARZ3NDEKTSV4RRFFQ69G5FAV")
    assert res.status_code == 404


def test_read_only_no_mutations_exposed(seeded_client: TestClient) -> None:
    schema = seeded_client.get("/openapi.json").json()
    catalog_paths = [p for p in schema["paths"] if p.startswith("/catalog")]
    assert catalog_paths, "catalog paths must exist"
    for path in catalog_paths:
        methods = set(schema["paths"][path].keys())
        assert methods <= {"get"}, f"{path} must be read-only, found {methods}"
