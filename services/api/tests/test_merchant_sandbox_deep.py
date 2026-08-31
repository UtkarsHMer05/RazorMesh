"""Deep-engine correction (G012-G015) acceptance: Merchant Sandbox truth.

Proves:
- G012: an immutable TransactionBaseline is captured at proposal time and
  the authorized side of every diff comes from it — changing the shared
  Product row CANNOT change the authorized/original diff;
- G013: condition downgrade and merchant swap are checkout-local; the
  shared catalog Product row is never mutated (one mission cannot corrupt
  the catalog for another);
- G014: revert restores the EXACT pre-mutation baseline (original
  condition — never a hardcoded "new" — original merchant, quantity, fees,
  shipping, recurring, display text, unit price), while the mutation AND
  the revert both remain in the audit ledger;
- G015: a merchant checkout created for the CURRENT mission intent binds
  to that mission's trace (response carries trace_id; the same trace
  resolves across surfaces).
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select

from conftest import wipe_business_tables
from razormesh_api.catalog import seed_catalog
from razormesh_api.ledger import EvidenceLedger
from razormesh_api.merchant_sandbox import (
    MerchantDemoError,
    MutationKind,
    apply_mutation,
    offer_diff,
    propose_checkout_for_demo,
)
from razormesh_api.persistence.db import create_session_factory
from razormesh_api.persistence.models import (
    Checkout as RowCheckout,
)
from razormesh_api.persistence.models import (
    IntentContract as RowIntent,
)
from razormesh_api.persistence.models import Product, TransactionBaseline
from razormesh_api.persistence.repositories import Repositories, session_scope
from razormesh_api.trace_registry import TraceRegistry


@pytest.fixture()
def merchant_local_client(settings):  # type: ignore[no-untyped-def]
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


def _setup(settings):  # type: ignore[no-untyped-def]
    """Isolated per-test state: wipe, then seed the full 5-merchant catalog.

    Other suites (e.g. the protocol playground's scenario-c) merge the
    single Security-Lab demo merchant into the shared test DB; seed_catalog
    would then no-op with a 1-merchant catalog and merchant-swap would have
    no target. Wiping first guarantees the full catalog for every test.
    """
    engine = create_engine(settings.database_url, future=True)
    repos = Repositories(create_session_factory(engine))
    wipe_business_tables(engine)
    seed_catalog(repos)
    ledger = EvidenceLedger(repos)
    return repos, ledger


def _product(repos: Repositories) -> str:
    """A non-recurring product (fallback: the first product)."""
    with session_scope(repos.factory) as session:
        product = (
            session.execute(select(Product).where(Product.recurring.is_(False)).limit(1))
            .scalars()
            .first()
        )
        if product is None:
            product = session.execute(select(Product).limit(1)).scalars().first()
        assert product is not None, "catalog must have products"
        return product.id


# ---------------------------------------------------------------------------
# G012 — immutable baseline
# ---------------------------------------------------------------------------


def test_baseline_captured_at_proposal_time(settings) -> None:  # type: ignore[no-untyped-def]
    repos, _ledger = _setup(settings)
    pid = _product(repos)
    intent_id, checkout_id, _ = propose_checkout_for_demo(repos, product_id=pid)
    with session_scope(repos.factory) as session:
        base = session.execute(
            select(TransactionBaseline).where(TransactionBaseline.checkout_id == checkout_id)
        ).scalar_one()
        row = session.get(RowCheckout, checkout_id)
    assert base.intent_id == intent_id
    assert base.quantity == 1
    assert base.total_minor == row.computed_total_minor
    # one baseline per checkout (unique constraint + idempotent capture)
    assert base.id == f"base_{checkout_id}"


def test_changing_product_row_cannot_change_authorized_diff(settings) -> None:  # type: ignore[no-untyped-def]
    """THE G012 proof: mutate the shared catalog row; the authorized side of
    the diff must be unchanged (it comes from the baseline, not the product)."""
    repos, _ledger = _setup(settings)
    pid = _product(repos)
    _intent_unused, checkout_id, _ = propose_checkout_for_demo(repos, product_id=pid)

    # pre-mutation diff is empty (checkout matches its baseline)
    assert offer_diff(repos, checkout_id)["diff"] == []

    # adversarially change the SHARED product row's price + condition
    with session_scope(repos.factory) as session:
        product = session.get(Product, pid)
        product.price_minor = 999_900
        product.condition = "refurbished"

    # the authorized side still reflects the ORIGINAL proposal
    diff = offer_diff(repos, checkout_id)["diff"]
    assert diff == [], "a catalog change must not create transaction drift"


def test_diff_uses_baseline_not_current_product(settings) -> None:  # type: ignore[no-untyped-def]
    """After a price-drift mutation AND a product-row change, the diff's
    authorized value must be the baseline (original unit price), not the
    mutated catalog price."""
    repos, ledger = _setup(settings)
    pid = _product(repos)
    intent_id, checkout_id, _ = propose_checkout_for_demo(repos, product_id=pid)
    apply_mutation(
        repos, ledger, intent_id=intent_id, checkout_id=checkout_id, kind=MutationKind.PRICE_DRIFT
    )
    with session_scope(repos.factory) as session:
        original_unit = (
            session.execute(
                select(TransactionBaseline).where(TransactionBaseline.checkout_id == checkout_id)
            )
            .scalar_one()
            .unit_price_minor
        )
    diff = offer_diff(repos, checkout_id)["diff"]
    price_row = next(d for d in diff if d["field"] == "unit_price_minor")
    assert price_row["authorized"] == original_unit
    assert price_row["current"] == original_unit + 50_000


# ---------------------------------------------------------------------------
# G013 — checkout-local mutations (no shared catalog writes)
# ---------------------------------------------------------------------------


def test_condition_downgrade_is_checkout_local(settings) -> None:  # type: ignore[no-untyped-def]
    """Condition downgrade must NOT write the shared Product row."""
    repos, ledger = _setup(settings)
    pid = _product(repos)
    intent_id, checkout_id, _ = propose_checkout_for_demo(repos, product_id=pid)
    with session_scope(repos.factory) as session:
        original_condition = session.get(Product, pid).condition

    apply_mutation(
        repos,
        ledger,
        intent_id=intent_id,
        checkout_id=checkout_id,
        kind=MutationKind.CONDITION_DOWNGRADE,
    )
    with session_scope(repos.factory) as session:
        product = session.get(Product, pid)
        row = session.get(RowCheckout, checkout_id)
    # the catalog row is UNTOUCHED — one mission cannot corrupt the catalog
    assert product.condition == original_condition
    # the checkout snapshot carries the downgrade
    lines = list(row.line_items or [])
    assert lines[0]["condition"] == "used"
    # the diff sees it (vs the baseline)
    diff = offer_diff(repos, checkout_id)["diff"]
    assert any(d["field"] == "condition" and d["current"] == "used" for d in diff)


def test_merchant_swap_is_checkout_local(settings) -> None:  # type:  ignore[type-arg]  # type: ignore[no-untyped-def]
    """Merchant substitution must not create or mutate any catalog rows."""
    repos, ledger = _setup(settings)
    pid = _product(repos)
    intent_id, checkout_id, _ = propose_checkout_for_demo(repos, product_id=pid)
    with session_scope(repos.factory) as session:
        merchants_before = sorted(
            m for (m,) in session.execute(select(Product.merchant_id).distinct())
        )

    apply_mutation(
        repos,
        ledger,
        intent_id=intent_id,
        checkout_id=checkout_id,
        kind=MutationKind.MERCHANT_SWAP,
    )
    with session_scope(repos.factory) as session:
        merchants_after = sorted(
            m for (m,) in session.execute(select(Product.merchant_id).distinct())
        )
        row = session.get(RowCheckout, checkout_id)
    assert merchants_before == merchants_after  # catalog untouched
    assert row.merchant_id != (
        session.execute(
            select(TransactionBaseline).where(TransactionBaseline.checkout_id == checkout_id)
        )
        .scalar_one()
        .merchant_id
    )


def test_one_mission_cannot_corrupt_catalog_for_another(settings) -> None:  # type: ignore[no-untyped-def]
    """Mission A's mutations leave the catalog pristine for mission B."""
    repos, ledger = _setup(settings)
    pid = _product(repos)
    with session_scope(repos.factory) as session:
        before = sorted(
            (p.id, p.condition, p.price_minor) for p in session.execute(select(Product)).scalars()
        )

    for kind in (
        MutationKind.PRICE_DRIFT,
        MutationKind.HIDDEN_FEE,
        MutationKind.HIDDEN_MEMBERSHIP,
        MutationKind.CONDITION_DOWNGRADE,
        MutationKind.MERCHANT_SWAP,
        MutationKind.QUANTITY_INCREASE,
        MutationKind.HOSTILE_INSTRUCTION,
    ):
        i2, c2, _ = propose_checkout_for_demo(repos, product_id=pid)
        apply_mutation(repos, ledger, intent_id=i2, checkout_id=c2, kind=kind)

    with session_scope(repos.factory) as session:
        after = sorted(
            (p.id, p.condition, p.price_minor) for p in session.execute(select(Product)).scalars()
        )
    assert before == after, "no mission may mutate shared catalog state"


# ---------------------------------------------------------------------------
# G014 — exact revert (property-style)
# ---------------------------------------------------------------------------


_ALL_PRESET_COMBOS: list[tuple[MutationKind, ...]] = [
    (MutationKind.PRICE_DRIFT,),
    (MutationKind.HIDDEN_FEE,),
    (MutationKind.HIDDEN_MEMBERSHIP,),
    (MutationKind.CONDITION_DOWNGRADE,),
    (MutationKind.MERCHANT_SWAP,),
    (MutationKind.QUANTITY_INCREASE,),
    (MutationKind.HOSTILE_INSTRUCTION,),
    (
        MutationKind.PRICE_DRIFT,
        MutationKind.HIDDEN_FEE,
        MutationKind.HIDDEN_MEMBERSHIP,
        MutationKind.CONDITION_DOWNGRADE,
    ),
    (MutationKind.QUANTITY_INCREASE, MutationKind.MERCHANT_SWAP),
]


@pytest.mark.parametrize("combo", _ALL_PRESET_COMBOS, ids=[str(c) for c in _ALL_PRESET_COMBOS])
def test_revert_restores_exact_baseline(settings, combo) -> None:  # type: ignore[no-untyped-def]
    """Property: baseline -> apply arbitrary preset(s) -> revert == baseline."""
    repos, ledger = _setup(settings)
    pid = _product(repos)
    intent_id, checkout_id, _ = propose_checkout_for_demo(repos, product_id=pid)

    def current_snapshot() -> dict:  # type: ignore[no-untyped-def]
        with session_scope(repos.factory) as session:
            row = session.get(RowCheckout, checkout_id)
            lines = list(row.line_items or [])
            return {
                "merchant_id": row.merchant_id,
                "condition": lines[0].get("condition"),
                "quantity": lines[0].get("quantity"),
                "unit_price_minor": lines[0].get("unit_price_minor"),
                "display_name": lines[0].get("display_name"),
                "fees_minor": row.fees_minor,
                "shipping_minor": row.shipping_minor,
                "subscription_terms": dict(row.subscription_terms)
                if row.subscription_terms
                else None,
            }

    baseline_snapshot = current_snapshot()

    for kind in combo:
        apply_mutation(repos, ledger, intent_id=intent_id, checkout_id=checkout_id, kind=kind)
    assert current_snapshot() != baseline_snapshot, "mutation must change something"

    apply_mutation(
        repos, ledger, intent_id=intent_id, checkout_id=checkout_id, kind=MutationKind.REVERT
    )
    assert current_snapshot() == baseline_snapshot, (
        f"revert must restore the EXACT baseline after {combo}"
    )
    # the diff against the baseline is now empty again
    assert offer_diff(repos, checkout_id)["diff"] == []


def test_revert_restores_original_condition_not_hardcoded_new(
    settings,
) -> None:  # ignore[type-arg]  # type: ignore[no-untyped-def]
    """The old bug: revert forced condition to 'new'. Instead it must restore
    the ORIGINAL condition — proven on a product that was NOT new."""
    repos, ledger = _setup(settings)
    with session_scope(repos.factory) as session:
        used_product = session.execute(
            select(Product).where(Product.condition == "used").limit(1)
        ).scalar_one_or_none()
        if used_product is None:
            # make a deterministic used-condition product in the LOCAL sandbox
            any_product = session.execute(select(Product).limit(1)).scalar_one()
            any_product.condition = "used"
            pid = any_product.id
        else:
            pid = used_product.id

    intent_id, checkout_id, _ = propose_checkout_for_demo(repos, product_id=pid)
    apply_mutation(
        repos,
        ledger,
        intent_id=intent_id,
        checkout_id=checkout_id,
        kind=MutationKind.CONDITION_DOWNGRADE,
    )
    # downgrade preset targets 'used'; ensure something changed or force it
    apply_mutation(
        repos, ledger, intent_id=intent_id, checkout_id=checkout_id, kind=MutationKind.REVERT
    )
    with session_scope(repos.factory) as session:
        base = session.execute(
            select(TransactionBaseline).where(TransactionBaseline.checkout_id == checkout_id)
        ).scalar_one()
        row = session.get(RowCheckout, checkout_id)
    lines = list(row.line_items or [])
    assert lines[0]["condition"] == base.condition
    if base.condition == "used":
        assert lines[0]["condition"] == "used", (
            "revert must restore the ORIGINAL condition, not force 'new'"
        )


def test_mutation_and_revert_both_remain_in_audit(settings) -> None:  # type: ignore[no-untyped-def]
    """History is not erased by revert: both events persist."""
    repos, ledger = _setup(settings)
    pid = _product(repos)
    intent_id, checkout_id, _ = propose_checkout_for_demo(repos, product_id=pid)
    apply_mutation(
        repos, ledger, intent_id=intent_id, checkout_id=checkout_id, kind=MutationKind.PRICE_DRIFT
    )
    apply_mutation(
        repos, ledger, intent_id=intent_id, checkout_id=checkout_id, kind=MutationKind.REVERT
    )
    events = TraceRegistry(repos)
    trace = events.by_intent(intent_id)
    assert trace is not None
    from razormesh_api.trace_registry import project_events

    projected = project_events(repos, intent_id)
    kinds = [e.kind for e in projected]
    assert "offer.mutated" in kinds
    assert "offer.reverted" in kinds


# ---------------------------------------------------------------------------
# G015 — current-trace binding
# ---------------------------------------------------------------------------


def test_checkout_for_current_intent_returns_same_trace(settings) -> None:  # type: ignore[no-untyped-def]
    """A checkout created for the CURRENT mission's intent resolves to the
    SAME trace — the response carries trace_id (no silent disconnection)."""
    repos, ledger = _setup(settings)
    pid = _product(repos)
    intent_id, _checkout_id_unused, _ = propose_checkout_for_demo(repos, product_id=pid)
    first_trace = TraceRegistry(repos).by_intent(intent_id)
    assert first_trace is not None

    intent_id2, checkout_id2, _ = propose_checkout_for_demo(
        repos, product_id=pid, intent_id=intent_id
    )
    assert intent_id2 == intent_id  # the CURRENT mission, not a new one
    second_trace = TraceRegistry(repos).by_intent(intent_id2)
    assert second_trace is not None
    assert second_trace.trace_id == first_trace.trace_id

    # mutation on the new checkout reports the same trace
    result = apply_mutation(
        repos,
        ledger,
        intent_id=intent_id2,
        checkout_id=checkout_id2,
        kind=MutationKind.PRICE_DRIFT,
    )
    assert result.trace_id == first_trace.trace_id


def test_api_response_carries_trace_id(merchant_local_client: TestClient) -> None:
    items = merchant_local_client.get("/catalog/products", params={"limit": 50}).json()["items"]
    pid = next(p["id"] for p in items if not p.get("recurring"))
    res = merchant_local_client.post(
        "/merchant-sandbox/checkout", json={"product_id": pid, "quantity": 1}
    )
    assert res.status_code == 200
    body = res.json()
    assert body["trace_id"], "response must carry the trace id (G015)"
    # mutating that checkout reports the same trace id
    mut = merchant_local_client.post(
        "/merchant-sandbox/mutate",
        json={
            "intent_id": body["intent_id"],
            "checkout_id": body["checkout_id"],
            "kind": "price_drift",
        },
    )
    assert mut.status_code == 200
    assert mut.json()["trace_id"] == body["trace_id"]


def test_baseline_missing_is_clean_409(merchant_local_client: TestClient) -> None:
    """A checkout with no baseline (pre-correction rows) fails closed with a
    clean error — never a silent diff against mutable product state."""
    from datetime import UTC, datetime, timedelta

    from razormesh_api.settings import get_settings

    settings = get_settings()
    engine = create_engine(settings.database_url, future=True)
    repos = Repositories(create_session_factory(engine))
    ledger = EvidenceLedger(repos)
    import uuid

    fake_intent = f"intent_{uuid.uuid4().hex[:26].upper()}"
    now = datetime.now(UTC)
    with session_scope(repos.factory) as session:
        session.add(
            RowIntent(
                intent_id=fake_intent,
                principal_id="usr_x",
                agent_id="agt_x",
                authorization_generation=1,
                status="AUTHORIZED",
                currency="INR",
                recurring_allowed=False,
                max_total_minor=50_000_000,
                aggregate_budget_minor=200_000_000,
                max_quantity=2,
                approval_threshold_minor=40_000_000,
                issued_at=now,
                authorized_at=now,
                expires_at=now + timedelta(minutes=30),
                created_at=now,
                updated_at=now,
            )
        )
    pid = _product(repos)
    intent_id, checkout_id, _ = propose_checkout_for_demo(repos, product_id=pid)
    # delete the baseline to simulate a pre-correction checkout
    with session_scope(repos.factory) as session:
        base = session.execute(
            select(TransactionBaseline).where(TransactionBaseline.checkout_id == checkout_id)
        ).scalar_one()
        session.delete(base)
    with pytest.raises(MerchantDemoError) as excinfo:
        apply_mutation(
            repos,
            ledger,
            intent_id=intent_id,
            checkout_id=checkout_id,
            kind=MutationKind.PRICE_DRIFT,
        )
    assert excinfo.value.code == "BASELINE_MISSING"
