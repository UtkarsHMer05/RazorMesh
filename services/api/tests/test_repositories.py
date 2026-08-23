"""M21 acceptance: repository layer + transaction rollback + concurrency lock."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine

from razormesh_api.domain.ids import IntentId, MerchantId, ProductId
from razormesh_api.persistence import models  # noqa: F401
from razormesh_api.persistence.db import create_session_factory
from razormesh_api.persistence.models import (
    AuthorizationSpend,
    IntentContract,
    Merchant,
    Product,
)
from razormesh_api.persistence.repositories import (
    ConcurrencyConflict,
    Repositories,
)


def _make_engine():
    from razormesh_api.settings import get_settings

    url = get_settings().database_url
    engine = create_engine(url, future=True)
    return engine


@pytest.fixture()
def repos():
    engine = _make_engine()
    factory = create_session_factory(engine)
    r = Repositories(factory)
    yield r
    # cleanup between tests
    with r.transaction() as s:
        s.query(AuthorizationSpend).delete()
        s.query(IntentContract).delete()
        s.query(Product).delete()
        s.query(Merchant).delete()


def _merchant(mid: MerchantId) -> Merchant:
    now = datetime.now(UTC)
    return Merchant(
        id=str(mid),
        name="Demo Merchant",
        display_name="Demo",
        created_at=now,
        updated_at=now,
    )


def _product(mid: MerchantId, pid: ProductId) -> Product:
    now = datetime.now(UTC)
    return Product(
        id=str(pid),
        merchant_id=str(mid),
        title="Headphones",
        description="Sony WH-1000XM5",
        brand="Sony",
        category="audio",
        condition="new",
        price_minor=479900,
        currency="INR",
        shipping_minor=0,
        tax_minor=0,
        fees_minor=0,
        recurring=False,
        created_at=now,
        updated_at=now,
    )


def _intent(iid: IntentId) -> IntentContract:
    now = datetime.now(UTC)
    return IntentContract(
        intent_id=str(iid),
        principal_id="usr_demo",
        agent_id="agt_demo",
        authorization_generation=1,
        status="AUTHORIZED",
        currency="INR",
        max_total_minor=500000,
        aggregate_budget_minor=2000000,
        max_quantity=2,
        recurring_allowed=False,
        approval_threshold_minor=400000,
        issued_at=now - timedelta(minutes=10),
        authorized_at=now - timedelta(minutes=5),
        expires_at=now + timedelta(minutes=60),
        created_at=now,
        updated_at=now,
    )


def test_merchant_and_product_roundtrip(repos: Repositories) -> None:
    m = repos.merchants.save(_merchant(MerchantId("mrc_TESTR0VND00000000000000000")))
    p = repos.products.save(_product(m.id, ProductId("prd_TESTR0VND00000000000000000")))
    assert repos.products.get(ProductId(p.id)) is not None
    assert len(repos.products.list_by_merchant(MerchantId(m.id))) == 1
    assert len(repos.merchants.list()) == 1


def test_intent_save0000000000000000000000_and_fetch(repos: Repositories) -> None:
    iid = IntentId("intent_TESTR0VND00000000000000000")
    repos.intents.save(_intent(iid))
    assert repos.intents.get(iid) is not None


def test_spend_reservation_commit_release_semantics(repos: Repositories) -> None:
    iid = IntentId("intent_TESTSPEND00000000000000000")
    repos.intents.save(_intent(iid))
    repos.spend.ensure(iid, authorized_minor=1_000_000)
    assert repos.spend.available_minor(iid) >= 0
    with repos.transaction() as s:
        row = repos.spend.get_for_update(iid, s)
        assert row is not None
        row.reserved_minor += 300000
    assert repos.spend.available_minor(iid) == 700000


def test_transaction_rollback_on_error(repos: Repositories) -> None:
    iid = IntentId("intent_TESTR011BK0000000000000000")
    repos.intents.save(_intent(iid))
    with pytest.raises(ValueError):
        with repos.transaction():
            repos.spend.ensure(iid, authorized_minor=500000)
            raise ValueError("simulated failure")
    # rollback: only the spend reservation was inside the failed txn; the
    # intent was committed in a prior (separate) transaction. Verify the
    # failed reservation did NOT persist (available == authorized, no reserved).
    assert repos.spend.available_minor(iid) == 500000


def test_concurrent_reservation_does_not_overspend() -> None:
    """Real concurrency: parallel threads reserve atomically under row lock."""
    from threading import Thread

    engine = _make_engine()
    factory = create_session_factory(engine)
    r = Repositories(factory)
    iid = IntentId("intent_TESTC0NCVRR000000000000000")
    with r.transaction() as s:
        s.query(AuthorizationSpend).delete()
        s.query(IntentContract).delete()
    r.intents.save(_intent(iid))
    r.spend.ensure(iid, authorized_minor=1_000_000)

    results: list[str] = []
    limit = 400000

    def worker() -> None:
        try:
            with r.transaction() as s:
                row = r.spend.get_for_update(iid, s)
                available = row.authorized_minor - row.reserved_minor - row.committed_minor
                if available < limit:
                    raise ConcurrencyConflict("insufficient")
                row.reserved_minor += limit
                results.append("reserved")
        except ConcurrencyConflict:
            results.append("rejected")

    threads = [Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # 1_000_000 / 400_000 = at most 2 reservations succeed; rest rejected
    assert results.count("reserved") == 2
    assert results.count("rejected") == 3
    assert r.spend.available_minor(iid) == 200000
