"""M30: subscription / expiry / approval-challenge rules.

- Recurring checkouts require explicit recurring permission in the intent.
- Expired authorizations fail hard (AUTHORIZATION_EXPIRED).
- Totals strictly ABOVE the approval threshold produce UNKNOWN with
  APPROVAL_REQUIRED: a deterministic CHALLENGE signal — the decision engine
  (M32) must never ALLOW while it is present; reauthorization clears it.

Boundaries:
- total == approval_threshold          -> PASS (at threshold is pre-approved)
- total == approval_threshold + 1      -> UNKNOWN APPROVAL_REQUIRED
- now == expires_at                    -> FAIL (expiry is inclusive-dead)
"""

from collections.abc import Callable

from razormesh_api.rules.engine import (
    EvaluationContext,
    FunctionRule,
    RuleOutcome,
    RuleResult,
)


def _rule(rule_id: str, fn: "Callable[[EvaluationContext], RuleResult]") -> FunctionRule:
    return FunctionRule(rule_id, fn)


def _outcome(
    rule_id: str,
    *,
    ok: bool,
    fail_code: str,
    explanation: str,
) -> RuleResult:
    return RuleResult(
        rule_id=rule_id,
        outcome=RuleOutcome.PASS if ok else RuleOutcome.FAIL,
        reason_codes=() if ok else (fail_code,),
        explanation=explanation if not ok else "",
    )


def _recurring_view(ctx: EvaluationContext) -> RuleResult:
    is_recurring = ctx.checkout.has_recurring_terms()
    if not is_recurring:
        return _outcome("policy.recurring_permission", ok=True, fail_code="", explanation="")
    if ctx.intent.recurring_allowed:
        return _outcome("policy.recurring_permission", ok=True, fail_code="", explanation="")
    return _outcome(
        "policy.recurring_permission",
        ok=False,
        fail_code="RECURRING_NOT_ALLOWED",
        explanation="checkout contains recurring terms but the authorization "
        "does not permit subscriptions",
    )


recurring_permission_rule = _rule("policy.recurring_permission", _recurring_view)


def _expiry_view(ctx: EvaluationContext) -> RuleResult:
    now = ctx.effective_now()
    expired = now >= ctx.intent.expires_at
    return _outcome(
        "policy.not_expired",
        ok=not expired,
        fail_code="AUTHORIZATION_EXPIRED",
        explanation=f"authorization expired at "
        f"{ctx.intent.expires_at.isoformat()} (now {now.isoformat()})",
    )


not_expired_rule = _rule("policy.not_expired", _expiry_view)


def _approval_view(ctx: EvaluationContext) -> RuleResult:
    total = ctx.checkout.compute_total().amount_minor
    threshold = ctx.intent.approval_threshold.amount_minor
    if total <= threshold:
        return RuleResult(
            rule_id="policy.approval_threshold",
            outcome=RuleOutcome.PASS,
            reason_codes=(),
            explanation="",
        )
    # Above the human's pre-approval line: deterministic CHALLENGE signal.
    return RuleResult(
        rule_id="policy.approval_threshold",
        outcome=RuleOutcome.UNKNOWN,
        reason_codes=("APPROVAL_REQUIRED",),
        explanation=f"payable {total} exceeds pre-approved threshold {threshold}; "
        "human step-up required before execution",
        details={"payable_minor": total, "threshold_minor": threshold},
    )


approval_threshold_rule = _rule("policy.approval_threshold", _approval_view)


POLICY_RULES = (
    recurring_permission_rule,
    not_expired_rule,
    approval_threshold_rule,
)
