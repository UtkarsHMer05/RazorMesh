"""M18 acceptance: CheckoutEnvelope recomputation + rejection rules."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from razormesh_api.domain.checkout import (
    BoundedText,
    CheckoutEnvelope,
    LineItem,
    SubscriptionTerms,
)
from razormesh_api.domain.ids import new_ulid
from razormesh_api.domain.money import Money
from razormesh_api.domain.provenance import Provenanced


def item(qty: int = 1, unit: int = 479900) -> LineItem:
    name = Provenanced[BoundedText].model_construct(
        value=BoundedText(text="Sony WH-1000XM5 headphones"),
        trust_class="UNTRUSTED_CONTENT",
        source_type="MERCHANT_FREE_TEXT",
        source_id="catalog",
        observed_at=datetime.now(UTC),
    )
    return LineItem(
        product_id=f"prd_{new_ulid()}",
        display_name=name,
        quantity=qty,
        unit_price=Money(unit),
        condition="new",
    )


def envelope(
    items: tuple[LineItem, ...] | None = None,
    tax: int = 0,
    shipping: int = 0,
    fees: int = 0,
    provided_total: int | None = None,
    subscription: SubscriptionTerms | None = None,
) -> CheckoutEnvelope:
    its = items if items is not None else (item(),)
    if provided_total is None:
        computed = Money.zero("INR")
        for it_ in its:
            computed = computed.add(it_.unit_price.multiply_positive_int(it_.quantity))
        total = computed.add(Money(tax)).add(Money(shipping)).add(Money(fees))
        amount = total.amount_minor
    else:
        amount = provided_total
    return CheckoutEnvelope(
        checkout_id=f"chk_{new_ulid()}",
        revision=1,
        merchant_id=f"mrc_{new_ulid()}",
        line_items=its,
        tax=Money(tax),
        shipping=Money(shipping),
        fees=Money(fees),
        subscription_terms=subscription,
        provided_total=Money(amount),
        observed_at=datetime.now(UTC),
    )


def test_totals_recomputed_from_line_items_fees_shipping_tax() -> None:
    env = envelope(tax=8638, shipping=4990, fees=2500)
    expected = Money(479900).add(Money(8638)).add(Money(4990)).add(Money(2500))
    assert env.compute_total() == expected
    assert env.provided_total == expected


def test_quantity_multiplies_unit_price() -> None:
    two_items = envelope(items=(item(qty=2),), tax=0, shipping=0, fees=0)
    assert two_items.subtotal == Money(959800)


def test_provided_total_disagreement_rejected_loudly() -> None:
    with pytest.raises(ValidationError, match="disagrees with server-recomputed"):
        envelope(provided_total=1)


def test_currency_mixing_rejected() -> None:
    mixed_item = item()
    bad_name = Provenanced[BoundedText].model_construct(
        value=BoundedText(text="x"),
        trust_class="UNTRUSTED_CONTENT",
        source_type="MERCHANT_FREE_TEXT",
        source_id="c",
        observed_at=datetime.now(UTC),
    )
    usd_item = LineItem(
        product_id=mixed_item.product_id,
        display_name=bad_name,
        quantity=1,
        unit_price=Money(100, "USD"),
        condition=None,
    )
    with pytest.raises(ValidationError, match="mixes currencies"):
        envelope(items=(mixed_item, usd_item), provided_total=0)


def test_subscription_terms_flagged() -> None:
    plain = envelope()
    assert plain.has_recurring_terms() is False

    recurring = envelope(subscription=SubscriptionTerms(recurring=True, frequency="monthly"))
    assert recurring.has_recurring_terms()


def test_empty_line_items_rejected() -> None:
    with pytest.raises(ValidationError):
        envelope(items=())


def test_unbounded_text_rejected() -> None:
    with pytest.raises(ValidationError):
        BoundedText(text="x" * 501)
