"""M28 acceptance: money rules with exact boundary behavior."""

from datetime import UTC, datetime, timedelta

from razormesh_api.domain.checkout import BoundedText, CheckoutEnvelope, LineItem
from razormesh_api.domain.ids import IntentId, new_ulid
from razormesh_api.domain.intent import IntentContract
from razormesh_api.domain.money import Money
from razormesh_api.domain.provenance import Provenanced
from razormesh_api.rules.engine import EvaluationContext, RuleOutcome
from razormesh_api.rules.money_rules import (
    MONEY_RULES,
    aggregate_budget_rule,
    currency_match_rule,
    fee_sanity_rule,
    max_total_rule,
    positive_amount_rule,
    shipping_sanity_rule,
)


def _item(qty: int = 1, unit: int = 100000) -> LineItem:
    return LineItem(
        product_id=f"prd_{new_ulid()}",
        display_name=Provenanced[BoundedText].model_construct(
            value=BoundedText(text="x"),
            trust_class="UNTRUSTED_CONTENT",
            source_type="MERCHANT_FREE_TEXT",
            source_id="c",
            observed_at=datetime.now(UTC),
        ),
        quantity=qty,
        unit_price=Money(unit),
    )


def _envelope(unit: int = 100000, qty: int = 1, fees: int = 0, shipping: int = 0):
    its = (_item(qty=qty, unit=unit),)
    computed = Money.zero("INR")
    for it_ in its:
        computed = computed.add(it_.unit_price.multiply_positive_int(it_.quantity))
    total = computed.add(Money(0)).add(Money(shipping)).add(Money(fees))
    return CheckoutEnvelope(
        checkout_id=f"chk_{new_ulid()}",
        revision=1,
        merchant_id=f"mrc_{new_ulid()}",
        line_items=its,
        tax=Money(0),
        shipping=Money(shipping),
        fees=Money(fees),
        provided_total=total,
        observed_at=datetime.now(UTC),
    )


def _ctx(total: int, *, committed: int = 0, reserved: int = 0) -> EvaluationContext:
    now = datetime.now(UTC)
    intent = IntentContract(
        intent_id=IntentId.generate(),
        principal_id=f"usr_{new_ulid()}",
        agent_id=f"agt_{new_ulid()}",
        authorization_generation=1,
        currency="INR",
        max_total=Money(500000),
        aggregate_budget=Money(2000000),
        approval_threshold=Money(400000),
        issued_at=now,
        authorized_at=now,
        expires_at=now + timedelta(minutes=30),
    )
    env = _envelope()
    if env.compute_total().amount_minor != 100000:  # pragma: no cover - guard
        raise AssertionError("helper invariant broken")
    return EvaluationContext(
        intent=intent, checkout=env, committed_minor=committed, reserved_minor=reserved
    )


def test_max_total_boundary_inclusive_pass_exclusive_fail() -> None:
    # max_total == 500000; subtotal 100000 passes; craft over-cap via budget ctx
    ctx = _ctx(100000)
    assert max_total_rule.evaluate(ctx).outcome == RuleOutcome.PASS

    tight_intent = ctx.intent.model_copy(update={"max_total": Money(99999)})
    over = EvaluationContext(intent=tight_intent, checkout=ctx.checkout)
    res = max_total_rule.evaluate(over)
    assert res.outcome == RuleOutcome.FAIL
    assert "TOTAL_EXCEEDS_MAX" in res.reason_codes

    exact = EvaluationContext(
        intent=ctx.intent.model_copy(update={"max_total": Money(100000)}),
        checkout=ctx.checkout,
    )
    assert max_total_rule.evaluate(exact).outcome == RuleOutcome.PASS


def test_currency_mismatch_fails() -> None:
    ctx = _ctx(100000)
    # rebuild the same envelope denominated in USD
    from razormesh_api.domain.checkout import CheckoutEnvelope as Env

    it = ctx.checkout.line_items[0]
    usd_item = it.model_copy(update={"unit_price": Money(100000, "USD")})
    usd_checkout = Env(
        checkout_id=ctx.checkout.checkout_id,
        revision=1,
        merchant_id=ctx.checkout.merchant_id,
        line_items=(usd_item,),
        tax=Money(0, "USD"),
        shipping=Money(0, "USD"),
        fees=Money(0, "USD"),
        provided_total=Money(100000, "USD"),
        observed_at=ctx.checkout.observed_at,
    )
    res = currency_match_rule.evaluate(EvaluationContext(intent=ctx.intent, checkout=usd_checkout))
    assert res.outcome == RuleOutcome.FAIL
    assert "CURRENCY_MISMATCH" in res.reason_codes


def test_aggregate_budget_boundary_with_open_reservations() -> None:
    # limit 2,000,000; used = 1,900,000 + proposed 100,000 == limit exactly -> PASS
    ctx_exact = _ctx(100000, committed=1_500_000, reserved=400_000)
    assert aggregate_budget_rule.evaluate(ctx_exact).outcome == RuleOutcome.PASS

    # one minor unit less headroom -> FAIL
    intent_tight = ctx_exact.intent.model_copy(update={"aggregate_budget": Money(1_999_999)})
    ctx_over = EvaluationContext(
        intent=intent_tight,
        checkout=ctx_exact.checkout,
        committed_minor=1_500_000,
        reserved_minor=400_000,
    )
    res = aggregate_budget_rule.evaluate(ctx_over)
    assert res.outcome == RuleOutcome.FAIL
    assert "BUDGET_EXCEEDED" in res.reason_codes


def test_zero_amount_fails_strictly_positive() -> None:
    ctx = _ctx(100000)
    zero_env = _envelope(unit=0)
    res = positive_amount_rule.evaluate(EvaluationContext(intent=ctx.intent, checkout=zero_env))
    assert res.outcome == RuleOutcome.FAIL
    assert "ZERO_AMOUNT" in res.reason_codes


def test_fee_boundary_fees_equal_subtotal_pass_above_fails() -> None:
    ctx = _ctx(100000)
    equal = _envelope(fees=100000)
    assert (
        fee_sanity_rule.evaluate(EvaluationContext(intent=ctx.intent, checkout=equal)).outcome
        == RuleOutcome.PASS
    )

    above = _envelope(fees=100001)
    res = fee_sanity_rule.evaluate(EvaluationContext(intent=ctx.intent, checkout=above))
    assert res.outcome == RuleOutcome.FAIL
    assert "FEES_EXCEED_SUBTOTAL" in res.reason_codes


def test_shipping_boundary_10x_subtotal_pass_one_over_fails() -> None:
    ctx = _ctx(100000)
    at_limit = _envelope(shipping=1000000)
    assert (
        shipping_sanity_rule.evaluate(
            EvaluationContext(intent=ctx.intent, checkout=at_limit)
        ).outcome
        == RuleOutcome.PASS
    )

    over = _envelope(shipping=1000001)
    res = shipping_sanity_rule.evaluate(EvaluationContext(intent=ctx.intent, checkout=over))
    assert res.outcome == RuleOutcome.FAIL
    assert "SHIPPING_EXCESSIVE" in res.reason_codes


def test_money_rules_registry_is_complete_and_deterministic() -> None:
    ids = [r.rule_id for r in MONEY_RULES]
    assert len(set(ids)) == len(ids)
    ctx = _ctx(100000)
    outcomes = [r.evaluate(ctx).outcome for r in MONEY_RULES]
    assert outcomes == [RuleOutcome.PASS] * len(MONEY_RULES)
