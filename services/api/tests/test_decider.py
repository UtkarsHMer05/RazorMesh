"""M32 acceptance: deterministic ALLOW/CHALLENGE/BLOCK decision matrix."""

from datetime import UTC, datetime, timedelta

import pytest

from razormesh_api.decider import POLICY_VERSION, Decision, DecisionEngine
from razormesh_api.domain.checkout import BoundedText, CheckoutEnvelope, LineItem
from razormesh_api.domain.ids import IntentId, new_ulid
from razormesh_api.domain.intent import IntentContract
from razormesh_api.domain.money import Money
from razormesh_api.domain.provenance import Provenanced
from razormesh_api.rules.engine import (
    EvaluationContext,
    FunctionRule,
    RuleOutcome,
    RuleResult,
)


def _item(qty: int = 1) -> LineItem:
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
        unit_price=Money(100000),
    )


def _envelope():
    it = _item()
    return CheckoutEnvelope(
        checkout_id=f"chk_{new_ulid()}",
        revision=1,
        merchant_id=f"mrc_{new_ulid()}",
        line_items=(it,),
        tax=Money(0),
        shipping=Money(0),
        fees=Money(0),
        provided_total=Money(100000),
        observed_at=datetime.now(UTC),
    )


def _intent(status: str = "AUTHORIZED"):
    now = datetime.now(UTC)
    return IntentContract(
        intent_id=IntentId.generate(),
        principal_id=f"usr_{new_ulid()}",
        agent_id=f"agt_{new_ulid()}",
        authorization_generation=1,
        status=status,
        currency="INR",
        max_total=Money(500000),
        aggregate_budget=Money(2000000),
        approval_threshold=Money(400000),
        issued_at=now,
        authorized_at=now,
        expires_at=now + timedelta(minutes=30),
    )


def rule(rid: str, outcome: str, codes=("GENERIC",)) -> FunctionRule:
    def fn(ctx: EvaluationContext) -> RuleResult:
        return RuleResult(rule_id=rid, outcome=outcome, reason_codes=codes)

    return FunctionRule(rid, fn)


PASS = rule("p", RuleOutcome.PASS)
FAIL = rule("f", RuleOutcome.FAIL, ("HARD_NO",))
UNKNOWN = rule("u", RuleOutcome.UNKNOWN, ("NEEDS_HUMAN",))


def test_all_pass_allows() -> None:
    engine = DecisionEngine([PASS])
    out = engine.decide(intent=_intent(), checkout=_envelope())
    assert out.decision is Decision.ALLOW
    assert out.reason_codes == ()
    assert out.policy_version == POLICY_VERSION


def test_any_fail_blocks_with_reasons() -> None:
    engine = DecisionEngine([PASS, FAIL])
    out = engine.decide(intent=_intent(), checkout=_envelope())
    assert out.decision is Decision.BLOCK
    assert "HARD_NO" in out.reason_codes


def test_unknown_without_fail_challenges() -> None:
    engine = DecisionEngine([PASS, UNKNOWN])
    out = engine.decide(intent=_intent(), checkout=_envelope())
    assert out.decision is Decision.CHALLENGE
    assert "NEEDS_HUMAN" in out.reason_codes


def test_fail_wins_over_unknown_block_beats_challenge() -> None:
    engine = DecisionEngine([FAIL, UNKNOWN])
    out = engine.decide(intent=_intent(), checkout=_envelope())
    assert out.decision is Decision.BLOCK


@pytest.mark.parametrize(
    "status", ["BLOCKED", "CHALLENGED", "SUPERSEDED", "REVOKED", "EXPIRED", "DRAFT"]
)
def test_state_gate_non_authorized_status_blocks_regardless_of_rules(status: str) -> None:
    """BLOCKED never executes; CHALLENGE never executes before reauthorization."""
    engine = DecisionEngine([PASS])
    out = engine.decide(intent=_intent(status=status), checkout=_envelope())
    assert out.decision is Decision.BLOCK
    assert out.reason_codes[0] == "STATUS_NOT_EXECUTABLE"
    assert out.reason_codes[1] == status


def test_decision_is_deterministic() -> None:
    engine = DecisionEngine([FAIL, UNKNOWN])
    i, c = _intent(), _envelope()
    assert engine.decide(intent=i, checkout=c) == engine.decide(intent=i, checkout=c)


def test_duplicate_rules_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        DecisionEngine([PASS, PASS])
