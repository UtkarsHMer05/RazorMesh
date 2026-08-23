"""M28: deterministic money rules (amount / currency / fees / shipping / budget).

All boundaries are inclusive on the allowed side:
- total == max_total            -> PASS (the cap authorizes up to and including)
- total == max_total + 1        -> FAIL
- committed+reserved+total == aggregate_budget -> PASS; +1 -> FAIL

Rules read ONLY trusted context fields (intent contract + server-recomputed
totals); untrusted merchant text can never influence these outcomes.
"""

from collections.abc import Callable

from razormesh_api.rules.engine import (
    EvaluationContext,
    FunctionRule,
    RuleOutcome,
    RuleResult,
)

SHIPPING_SUBTOTAL_MULTIPLE = 10


def _rule(rule_id: str, fn: "Callable[[EvaluationContext], RuleResult]") -> FunctionRule:
    return FunctionRule(rule_id, fn)


def _outcome(
    rule_id: str,
    *,
    ok: bool,
    fail_code: str,
    explanation: str,
    details: dict[str, object] | None = None,
) -> RuleResult:
    return RuleResult(
        rule_id=rule_id,
        outcome=RuleOutcome.PASS if ok else RuleOutcome.FAIL,
        reason_codes=() if ok else (fail_code,),
        explanation=explanation if not ok else "",
        details=details or {},
    )


def _currency_view(ctx: EvaluationContext) -> RuleResult:
    total = ctx.checkout.compute_total()
    ok = total.currency == ctx.intent.currency
    return _outcome(
        "money.currency_match",
        ok=ok,
        fail_code="CURRENCY_MISMATCH",
        explanation=f"checkout currency {total.currency} != authorized {ctx.intent.currency}",
    )


currency_match_rule = _rule("money.currency_match", _currency_view)


def _max_total_view(ctx: EvaluationContext) -> RuleResult:
    total = ctx.checkout.compute_total()
    ok = total <= ctx.intent.max_total
    return _outcome(
        "money.max_total",
        ok=ok,
        fail_code="TOTAL_EXCEEDS_MAX",
        explanation=(
            f"payable {total.amount_minor} exceeds max_total {ctx.intent.max_total.amount_minor}"
        ),
    )


max_total_rule = _rule("money.max_total", _max_total_view)


def _budget_view(ctx: EvaluationContext) -> RuleResult:
    proposed = ctx.checkout.compute_total().amount_minor
    used = ctx.committed_minor + ctx.reserved_minor
    limit = ctx.intent.aggregate_budget.amount_minor
    ok = used + proposed <= limit
    return _outcome(
        "money.aggregate_budget",
        ok=ok,
        fail_code="BUDGET_EXCEEDED",
        explanation=(f"aggregate use {used} + proposed {proposed} exceeds budget {limit}"),
        details={"used_minor": used, "proposed_minor": proposed, "limit_minor": limit},
    )


aggregate_budget_rule = _rule("money.aggregate_budget", _budget_view)


def _positive_amount_view(ctx: EvaluationContext) -> RuleResult:
    total = ctx.checkout.compute_total().amount_minor
    return _outcome(
        "money.positive_amount",
        ok=total > 0,
        fail_code="ZERO_AMOUNT",
        explanation="payable amount must be strictly positive",
    )


positive_amount_rule = _rule("money.positive_amount", _positive_amount_view)


def _fee_sanity_view(ctx: EvaluationContext) -> RuleResult:
    """Fees may never exceed the merchandise subtotal they ride on."""
    env = ctx.checkout
    fees = env.fees.amount_minor
    subtotal = env.subtotal.amount_minor
    return _outcome(
        "money.fee_sanity",
        ok=fees <= subtotal,
        fail_code="FEES_EXCEED_SUBTOTAL",
        explanation=f"fees {fees} exceed subtotal {subtotal}",
    )


fee_sanity_rule = _rule("money.fee_sanity", _fee_sanity_view)


def _shipping_sanity_view(ctx: EvaluationContext) -> RuleResult:
    """Shipping above a fixed multiple of subtotal is structurally abusive.

    Boundary: shipping == 10 x subtotal passes; one minor unit more fails.
    A zero subtotal blocks any nonzero shipping (nothing to ship).
    """
    env = ctx.checkout
    shipping = env.shipping.amount_minor
    subtotal = env.subtotal.amount_minor
    ceiling = subtotal * SHIPPING_SUBTOTAL_MULTIPLE
    ok = shipping <= ceiling and not (subtotal == 0 and shipping > 0)
    return _outcome(
        "money.shipping_sanity",
        ok=ok,
        fail_code="SHIPPING_EXCESSIVE",
        explanation=f"shipping {shipping} exceeds allowed ceiling {ceiling} "
        f"for subtotal {subtotal}",
    )


shipping_sanity_rule = _rule("money.shipping_sanity", _shipping_sanity_view)


MONEY_RULES = (
    currency_match_rule,
    positive_amount_rule,
    max_total_rule,
    aggregate_budget_rule,
    fee_sanity_rule,
    shipping_sanity_rule,
)
