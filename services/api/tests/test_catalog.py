"""M22 acceptance: synthetic catalog seeding with variations, idempotent."""

import pytest
from sqlalchemy import create_engine

from razormesh_api.catalog import _MERCHANT_DEFS, seed_catalog
from razormesh_api.persistence import models  # noqa: F401
from razormesh_api.persistence.db import create_session_factory
from razormesh_api.persistence.models import Merchant, Product
from razormesh_api.persistence.repositories import Repositories


def _make_engine():
    from razormesh_api.settings import get_settings

    return create_engine(get_settings().database_url, future=True)


@pytest.fixture()
def repos():
    engine = _make_engine()
    r = Repositories(create_session_factory(engine))
    yield r
    with r.transaction() as s:
        s.query(Product).delete()
        s.query(Merchant).delete()


def test_seed_creates_merchants_and_products(repos: Repositories) -> None:
    count = seed_catalog(repos)
    assert count == 50
    assert len(_MERCHANT_DEFS) == 5
    assert len(repos.merchants.list(limit=10)) == 5
    products = repos.products.list(limit=100)
    assert len(products) == 50
    # second call is a no-op (idempotent)
    assert seed_catalog(repos) == 0
    assert len(repos.products.list(limit=100)) == 50


def test_catalog_variations_present(repos: Repositories) -> None:
    seed_catalog(repos)
    products = repos.products.list(limit=100)
    conditions = {p.condition for p in products}
    assert {"new", "refurbished", "used"} <= conditions
    recurring = [p for p in products if p.recurring]
    assert len(recurring) >= 3
    for p in recurring:
        assert p.recurring_frequency == "monthly"
        assert p.condition == "new"
    # price spread across tiers and shipping rule applied
    prices = sorted(p.price_minor for p in products)
    assert prices[0] < 50000 and prices[-1] > 400000
    expensive = [p for p in products if p.price_minor >= 200000]
    assert all(p.shipping_minor == 0 for p in expensive)


def test_catalog_filtering_by_category_and_brand(repos: Repositories) -> None:
    seed_catalog(repos)
    audio = repos.products.list(category="audio", limit=20)
    assert len(audio) == 10
    assert all(p.category == "audio" for p in audio)
    sony = repos.products.list(brand="Sony", limit=20)
    assert len(sony) >= 2
    assert all(p.brand == "Sony" for p in sony)
