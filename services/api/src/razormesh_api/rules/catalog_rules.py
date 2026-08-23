"""M29: merchant / product / category / brand / quantity rules.

Allowlist semantics follow the IntentContract (fail-closed per SEC-018):
- ``None``  -> the human explicitly authorized ANY (rule passes);
- empty set -> the human authorized NOTHING (everything fails);
- non-empty -> membership decides.

Unknown-data behavior: when a rule needs a structured fact (brand/category)
that the trusted catalog could not resolve, the outcome is UNKNOWN with a
``*_UNKNOWN`` reason code — never a silent PASS.
"""

from collections.abc import Callable

from razormesh_api.rules.engine import (
    EvaluationContext,
    FunctionRule,
    ProductFacts,
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
    details: dict[str, object] | None = None,
) -> RuleResult:
    return RuleResult(
        rule_id=rule_id,
        outcome=RuleOutcome.PASS if ok else RuleOutcome.FAIL,
        reason_codes=() if ok else (fail_code,),
        explanation=explanation if not ok else "",
        details=details or {},
    )


def _unknown(rule_id: str, reason: str, explanation: str) -> RuleResult:
    return RuleResult(
        rule_id=rule_id,
        outcome=RuleOutcome.UNKNOWN,
        reason_codes=(reason,),
        explanation=explanation,
    )


def _merchant_view(ctx: EvaluationContext) -> RuleResult:
    allowed = ctx.intent.allowed_merchant_ids
    if allowed is None:
        return _outcome("catalog.merchant_allowlist", ok=True, fail_code="", explanation="")
    merchant = ctx.checkout.merchant_id
    ok = merchant in allowed
    return _outcome(
        "catalog.merchant_allowlist",
        ok=ok,
        fail_code="MERCHANT_NOT_ALLOWED",
        explanation=f"merchant {merchant} is not in the authorized allowlist "
        f"({len(allowed)} entries)",
    )


merchant_allowlist_rule = _rule("catalog.merchant_allowlist", _merchant_view)


def _product_view(ctx: EvaluationContext) -> RuleResult:
    allowed = ctx.intent.allowed_product_ids
    if allowed is None:
        return _outcome("catalog.product_allowlist", ok=True, fail_code="", explanation="")
    bad = sorted(
        item.product_id.value for item in ctx.checkout.line_items if item.product_id not in allowed
    )
    return _outcome(
        "catalog.product_allowlist",
        ok=not bad,
        fail_code="PRODUCT_NOT_ALLOWED",
        explanation=f"products not in authorized allowlist: {bad}",
        details={"disallowed": bad},
    )


product_allowlist_rule = _rule("catalog.product_allowlist", _product_view)


def _category_view(ctx: EvaluationContext) -> RuleResult:
    allowed = ctx.intent.allowed_categories
    if allowed is None:
        return _outcome("catalog.category_rule", ok=True, fail_code="", explanation="")
    facts = ctx.product_facts or {}
    unknown: list[str] = []
    disallowed: list[str] = []
    for item in ctx.checkout.line_items:
        category = facts.get(item.product_id.value, ProductFacts()).category
        if category is None:
            unknown.append(item.product_id.value)
        elif category not in allowed:
            disallowed.append(f"{item.product_id.value}:{category}")
    if unknown:
        return _unknown(
            "catalog.category_rule",
            "CATEGORY_UNKNOWN",
            f"trusted category unavailable for products: {sorted(unknown)}",
        )
    return _outcome(
        "catalog.category_rule",
        ok=not disallowed,
        fail_code="CATEGORY_NOT_ALLOWED",
        explanation=f"categories outside authorization: {disallowed}",
        details={"disallowed": disallowed},
    )


category_rule = _rule("catalog.category_rule", _category_view)


def _brand_view(ctx: EvaluationContext) -> RuleResult:
    restriction = ctx.intent.brand_restriction
    if restriction is None:
        return _outcome("catalog.brand_restriction", ok=True, fail_code="", explanation="")
    facts = ctx.product_facts or {}
    unknown: list[str] = []
    violations: list[str] = []
    for item in ctx.checkout.line_items:
        brand = facts.get(item.product_id.value, ProductFacts()).brand
        if brand is None:
            unknown.append(item.product_id.value)
            continue
        if restriction.mode == "allow_only":
            if brand.lower() not in {b.lower() for b in restriction.brands}:
                violations.append(f"{item.product_id.value}:{brand}")
        elif brand.lower() in {b.lower() for b in restriction.brands}:
            violations.append(f"{item.product_id.value}:{brand}")
    if unknown:
        return _unknown(
            "catalog.brand_restriction",
            "BRAND_UNKNOWN",
            f"trusted brand unavailable for products: {sorted(unknown)}; "
            "cannot verify restriction, failing closed",
        )
    mode_desc = (
        "not on the allowed brand list"
        if restriction.mode == "allow_only"
        else "on the forbidden brand list"
    )
    return _outcome(
        "catalog.brand_restriction",
        ok=not violations,
        fail_code="BRAND_RESTRICTION_VIOLATED",
        explanation=f"items {mode_desc}: {violations}",
        details={"violations": violations},
    )


brand_restriction_rule = _rule("catalog.brand_restriction", _brand_view)


def _quantity_view(ctx: EvaluationContext) -> RuleResult:
    max_qty = ctx.intent.max_quantity
    over = [
        f"{item.product_id.value}:{item.quantity}"
        for item in ctx.checkout.line_items
        if item.quantity > max_qty
    ]
    total_units = sum(item.quantity for item in ctx.checkout.line_items)
    over_total = total_units > max_qty * len(ctx.checkout.line_items)
    return _outcome(
        "catalog.quantity_limit",
        ok=not over and not over_total,
        fail_code="QUANTITY_EXCEEDS_MAX",
        explanation=f"quantities exceed authorized maximum {max_qty}: {over or total_units}",
        details={"over": over, "total_units": total_units},
    )


quantity_rule = _rule("catalog.quantity_limit", _quantity_view)


CATALOG_RULES = (
    merchant_allowlist_rule,
    product_allowlist_rule,
    category_rule,
    brand_restriction_rule,
    quantity_rule,
)
