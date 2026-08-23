"""M30 acceptance: subscription / expiry / approval-challenge rules."""

from datetime import UTC, datetime, timedelta

from razormesh_api.domain.checkout import (
    BoundedText,
    CheckoutEnvelope,
    LineItem,
    SubscriptionTerms,
)
from razormesh_api.domain.ids import IntentId, new_ulid
from razormesh_api.domain.intent import IntentContract
from razormesh_api.domain.money import Money
from razormesh_api.domain.provenance import Provenanced
from razormesh_api.rules.engine import EvaluationContext, RuleOutcome
from razormesh_api.rules.policy_rules import (
    POLICY_RULES,
    approval_threshold_rule,
    not_expired_rule,
    recurring_permission_rule,
)

NOW = datetime.now(UTC)


def _item(qty: int = 1, unit: int = 400000) -> LineItem:
    return LineItem(
        product_id=f"prd_{new_ulid()}",
        display_name=Provenanced[BoundedText].model_construct(
            value=BoundedText(text="x"),
            trust_class="UNTRUSTED_CONTENT",
            source_type="MERCHANT_FREE_TEXT",
            source_id="c",
            observed_at=NOW,
        ),
        quantity=qty,
        unit_price=Money(unit),
    )


def _envelope(recurring: bool = False):  # type: ignore[no-untyped-def]
    it = _item()
    total = Money(400000)
    return CheckoutEnvelope(
        checkout_id=f"chk_{new_ulid()}",
        revision=1,
        merchant_id=f"mrc_{new_ulid()}",
        line_items=(it,),
        tax=Money(0),
        shipping=Money(0),
        fees=Money(0),
        subscription_terms=(
            SubscriptionTerms(recurring=True, frequency="monthly") if recurring else None
        ),
        provided_total=total,
        observed_at=NOW,
    )


def _intent(**overrides):  # type: ignore[no-untyped-def]
    defaults: dict = dict(
        intent_id=IntentId.generate(),
        principal_id=f"usr_{new_ulid()}",
        agent_id=f"agt_{new_ulid()}",
        authorization_generation=1,
        currency="INR",
        max_total=Money(500000),
        aggregate_budget=Money(2000000),
        approval_threshold=Money(400000),
        issued_at=NOW - timedelta(minutes=10),
        authorized_at=NOW - timedelta(minutes=5),
        expires_at=NOW + timedelta(minutes=30),
    )
    defaults.update(overrides)
    return IntentContract(**defaults)


def _ctx(intent=None, env=None, now=None):  # type: ignore[no-untyped-def]
    return EvaluationContext(
        intent=intent or _intent(),
        checkout=env or _envelope(),
        now_utc=now or NOW,
    )


def test_recurring_checkout_requires_explicit_permission() -> None:
    recurring_env = _envelope(recurring=True)
    denied = _intent(recurring_allowed=False)
    res = recurring_permission_rule.evaluate(
        EvaluationContext(intent=denied, checkout=recurring_env, now_utc=NOW)
    )
    assert res.outcome == RuleOutcome.FAIL
    assert "RECURRING_NOT_ALLOWED" in res.reason_codes

    allowed = _intent(recurring_allowed=True)
    assert (
        recurring_permission_rule.evaluate(
            EvaluationContext(intent=allowed, checkout=recurring_env, now_utc=NOW)
        ).outcome
        == RuleOutcome.PASS
    )


def test_non_recurring_checkout_needs_no_subscription_permission() -> None:
    plain_env = _envelope(recurring=False)
    strict = _intent(recurring_allowed=False)
    assert (
        recurring_permission_rule.evaluate(
            EvaluationContext(intent=strict, checkout=plain_env, now_utc=NOW)
        ).outcome
        == RuleOutcome.PASS
    )


def test_expiry_boundary_now_equal_expires_at_is_dead() -> None:
    intent = _intent(expires_at=NOW + timedelta(minutes=30))
    before = not_expired_rule.evaluate(
        EvaluationContext(intent=intent, checkout=_envelope(), now_utc=NOW + timedelta(minutes=29))
    )
    assert before.outcome == RuleOutcome.PASS

    at_edge = not_expired_rule.evaluate(
        EvaluationContext(intent=intent, checkout=_envelope(), now_utc=NOW + timedelta(minutes=30))
    )
    assert at_edge.outcome == RuleOutcome.FAIL
    assert "AUTHORIZATION_EXPIRED" in at_edge.reason_codes


def test_approval_threshold_challenge_boundary() -> None:
    # payable 400000 == threshold 400000 -> PASS (pre-approved up to threshold)
    ctx = _ctx()
    assert approval_threshold_rule.evaluate(ctx).outcome == RuleOutcome.PASS

    # one minor unit above -> UNKNOWN with APPROVAL_REQUIRED (challenge signal)
    pricier = _item(unit=400001)
    env_over = CheckoutEnvelope(
        checkout_id=f"chk_{new_ulid()}",
        revision=1,
        merchant_id=f"mrc_{new_ulid()}",
        line_items=(pricier,),
        tax=Money(0),
        shipping=Money(0),
        fees=Money(0),
        provided_total=Money(400001),
        observed_at=NOW,
    )
    res = approval_threshold_rule.evaluate(
        EvaluationContext(intent=_intent(), checkout=env_over, now_utc=NOW)
    )
    assert res.outcome == RuleOutcome.UNKNOWN
    assert "APPROVAL_REQUIRED" in res.reason_codes


def test_policy_registry_complete() -> None:
    ids = [r.rule_id for r in POLICY_RULES]
    assert len(set(ids)) == len(ids) == 3
