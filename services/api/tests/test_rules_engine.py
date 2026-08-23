"""M27 acceptance: deterministic composable rule engine foundation."""

from datetime import UTC, datetime

import pytest

from razormesh_api.domain.checkout import BoundedText, CheckoutEnvelope, LineItem
from razormesh_api.domain.ids import IntentId, new_ulid
from razormesh_api.domain.intent import IntentContract
from razormesh_api.domain.money import Money
from razormesh_api.domain.provenance import Provenanced
from razormesh_api.rules.engine import (
    AllOf,
    EvaluationContext,
    FunctionRule,
    RazorGuardEngine,
    RuleOutcome,
    RuleResult,
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


def _envelope(total_minor: int) -> CheckoutEnvelope:
    it = _item()
    return CheckoutEnvelope(
        checkout_id=f"chk_{new_ulid()}",
        revision=1,
        merchant_id=f"mrc_{new_ulid()}",
        line_items=(it,),
        tax=Money(0),
        shipping=Money(0),
        fees=Money(0),
        provided_total=Money(total_minor),
        observed_at=datetime.now(UTC),
    )


def _ctx(total_minor: int = 100000) -> EvaluationContext:
    now = datetime.now(UTC)
    intent = IntentContract(
        intent_id=IntentId.generate(),
        principal_id=f"usr_{new_ulid()}",
        agent_id=f"agt_{new_ulid()}",
        authorization_generation=1,
        currency="INR",
        max_total=Money(500000),
        aggregate_budget=Money(1000000),
        approval_threshold=Money(400000),
        issued_at=now,
        authorized_at=now,
        expires_at=now + timedelta(minutes=30),
    )
    return EvaluationContext(intent=intent, checkout=_envelope(total_minor))


def timedelta(minutes: int):  # type: ignore[no-untyped-def]
    from datetime import timedelta as td

    return td(minutes=minutes)


def pass_rule(rid: str = "pass") -> FunctionRule:
    return FunctionRule(rid, lambda ctx: RuleResult(rule_id=rid, outcome=RuleOutcome.PASS))


def fail_rule(rid: str = "fail", codes=("X",)) -> FunctionRule:  # type: ignore[assignment]
    def fn(ctx: EvaluationContext) -> RuleResult:
        return RuleResult(
            rule_id=rid,
            outcome=RuleOutcome.FAIL,
            reason_codes=codes,
            explanation="no",
        )

    return FunctionRule(rid, fn)


def unknown_rule(rid: str = "unk") -> FunctionRule:
    def fn(ctx: EvaluationContext) -> RuleResult:
        return RuleResult(rule_id=rid, outcome=RuleOutcome.UNKNOWN)

    return FunctionRule(rid, fn)


def test_engine_reports_every_rule_in_order() -> None:
    engine = RazorGuardEngine([pass_rule("r1"), pass_rule("r2")])
    report = engine.evaluate(_ctx())
    assert [r.rule_id for r in report.results] == ["r1", "r2"]
    assert all(r.outcome == RuleOutcome.PASS for r in report.results)
    assert report.passed


def test_fail_and_unknown_block_overall_pass() -> None:
    mixed = RazorGuardEngine([pass_rule("p"), fail_rule("f", ("TOO_EXPENSIVE",))])
    report = mixed.evaluate(_ctx())
    assert not report.passed
    assert report.reason_codes == ("TOO_EXPENSIVE",)

    with_unknown = RazorGuardEngine([pass_rule("p"), unknown_rule("u")])
    rep2 = with_unknown.evaluate(_ctx())
    assert not rep2.passed
    assert rep2.unknown[0].reason_codes == ()


def test_all_of_composite_first_fail_wins_with_reasons() -> None:
    combo = AllOf("combo", [pass_rule("a"), fail_rule("b", ("R1",)), fail_rule("c", ("R2",))])
    result = combo.evaluate(_ctx())
    assert result.outcome == RuleOutcome.FAIL
    assert set(result.reason_codes) >= {"R1", "R2"}
    assert set(result.details["failed_rules"]) == {"b", "c"}  # type: ignore[arg-type]


def test_crashing_rule_degrades_to_unknown_not_pass() -> None:
    def boom(ctx: EvaluationContext) -> RuleResult:
        raise RuntimeError("bug")

    engine = RazorGuardEngine([FunctionRule("boom", boom), pass_rule("ok")])
    report = engine.evaluate(_ctx())
    assert not report.passed
    assert report.results[0].outcome == RuleOutcome.UNKNOWN
    assert "RULE_ERROR" in report.results[0].reason_codes


def test_determinism_same_context_same_report() -> None:
    engine = RazorGuardEngine([pass_rule("p"), fail_rule("f"), unknown_rule("u")])
    ctx = _ctx()
    r1 = engine.evaluate(ctx)
    r2 = engine.evaluate(ctx)
    assert r1 == r2
    # and a fresh identical context produces identical outcomes per rule id
    r3 = engine.evaluate(_ctx())
    assert [(x.rule_id, x.outcome) for x in r3.results] == [
        (x.rule_id, x.outcome) for x in r1.results
    ]


def test_duplicate_rule_ids_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        RazorGuardEngine([pass_rule("same"), pass_rule("same")])


def test_invalid_outcome_rejected() -> None:
    with pytest.raises(ValueError, match="invalid rule outcome"):
        RuleResult(rule_id="bad", outcome="MAYBE")
