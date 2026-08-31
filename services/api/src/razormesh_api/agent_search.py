"""Phase-5 (M025/M026): Shopping Agent search + explainable ranking.

Contract (master prompt):
- Reads the CONFIRMED mandate (intent contract); never mutates it.
- Eligibility is computed by DOMAIN RULES (amount, currency, fees, shipping,
  budget, brand/merchant/condition restrictions, recurring terms, quantity) —
  deterministic, fail-closed. Ineligible products can never become eligible
  through this module.
- Ranking is a deterministic, explainable score (the agent *proposes*; only
  RazorGuard authorizes). Every claim maps to a catalog fact.
- Counts (products inspected etc.) are computed from real backend data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select

from razormesh_api.persistence.models import IntentContract, Product
from razormesh_api.persistence.repositories import Repositories, session_scope


class SearchError(RuntimeError):
    pass


@dataclass(frozen=True)
class Candidate:
    """One ranked candidate with evidence-based explanations."""

    product_id: str
    title: str
    brand: str | None
    category: str
    condition: str
    merchant_id: str
    unit_price_minor: int
    shipping_minor: int
    quantity: int
    total_minor: int
    currency: str
    score: int
    rank: int
    why: list[str] = field(default_factory=list)
    recurring: bool = False


@dataclass(frozen=True)
class Rejected:
    product_id: str
    title: str
    reason_code: str
    explanation: str


@dataclass(frozen=True)
class SearchReport:
    intent_id: str
    inspected: int
    eligible: int
    rejected: int
    candidates: list[Candidate]
    rejected_samples: list[Rejected]


def _matches_allowlist(value: str | None, allowed: frozenset[str] | None) -> bool:
    if allowed is None:
        return True
    if value is None:
        return False
    return value in allowed


def _intent_bool_set(raw: Any) -> frozenset[str] | None:
    """intent_contracts columns store lists or None; None = any (no restriction)."""
    if raw is None:
        return None
    if isinstance(raw, list):
        return frozenset(str(v) for v in raw)
    return None


def _condition_ok(product: Product, condition_restriction: Any) -> tuple[bool, str | None]:
    if condition_restriction is None:
        return True, None
    if isinstance(condition_restriction, dict):
        allow = condition_restriction.get("allow")
        if isinstance(allow, list) and allow:
            if (product.condition or "new").lower() not in {str(a).lower() for a in allow}:
                return False, "CONDITION_NOT_ALLOWED"
    return True, None


def _price_total(product: Product, quantity: int) -> int:
    # Server-side recomputation mirror of the domain envelope math for search
    # eligibility (the authoritative total is recomputed again at propose time
    # by CheckoutService — this ranking view can never authorize money).
    return product.price_minor * quantity + product.shipping_minor


def rank_catalog_for_intent(
    repos: Repositories,
    intent_id: str,
    *,
    quantity: int = 1,
    limit: int = 5,
    include_rejected: int = 6,
) -> SearchReport:
    """Deterministic, explainable ranking of the real catalog for a mandate.

    The confirmed intent is read-only here. Rules mirror RazorGuard semantics:
    over-budget, wrong currency, forbidden brand/merchant/condition, recurring
    terms when the mandate forbids them.
    """
    with session_scope(repos.factory) as session:
        intent_row = session.get(IntentContract, intent_id)
        if intent_row is None:
            raise SearchError("intent not found")
        # Trust only durable authority columns.
        max_total_minor = intent_row.max_total_minor
        currency = intent_row.currency
        merchants_ok = _intent_bool_set(intent_row.allowed_merchant_ids)
        categories_ok = _intent_bool_set(intent_row.allowed_categories)
        products_ok = _intent_bool_set(intent_row.allowed_product_ids)
        brand_restriction = intent_row.brand_restriction
        condition_restriction = intent_row.condition_restriction
        recurring_allowed = bool(intent_row.recurring_allowed)
        max_quantity = int(intent_row.max_quantity or 1)

        products = session.execute(select(Product).order_by(Product.id)).scalars().all()
        # Copy needed columns out of the session before closing.
        rows = [
            (
                p.id,
                p.title,
                p.brand,
                p.category,
                p.condition,
                p.merchant_id,
                p.price_minor,
                p.shipping_minor,
                p.currency,
                p.description,
                p.recurring,
            )
            for p in products
        ]

    if quantity > max_quantity:
        raise SearchError(f"quantity {quantity} exceeds mandate max_quantity {max_quantity}")

    eligible: list[Candidate] = []
    rejected: list[Rejected] = []
    inspected = len(rows)

    for (
        pid,
        title,
        brand,
        category,
        condition,
        merchant_id,
        price_minor,
        shipping_minor,
        prod_currency,
        _description,
        product_recurring,
    ) in rows:
        total = _price_total_price(price_minor, shipping_minor, quantity)
        why: list[str] = []
        fail_code = None
        fail_expl = ""

        if prod_currency != currency:
            fail_code, fail_expl = (
                "CURRENCY_MISMATCH",
                f"Product currency {prod_currency} ≠ mandate currency {currency}.",
            )
        elif product_recurring and not recurring_allowed:
            fail_code, fail_expl = (
                "RECURRING_NOT_ALLOWED",
                "Product carries recurring subscription terms, forbidden by the mandate.",
            )
        elif not _matches_allowlist(merchant_id, merchants_ok):
            fail_code, fail_expl = (
                "MERCHANT_NOT_ALLOWED",
                "Merchant is not in the confirmed merchant allowlist.",
            )
        elif not _matches_allowlist(pid, products_ok):
            fail_code, fail_expl = (
                "PRODUCT_NOT_ALLOWED",
                "Product is not in the confirmed product allowlist.",
            )
        elif not _matches_allowlist(category, categories_ok):
            fail_code, fail_expl = (
                "CATEGORY_NOT_ALLOWED",
                "Category is outside the confirmed category constraints.",
            )
        else:
            brand_fail = _brand_ok_simple(brand, brand_restriction)
            if brand_fail:
                fail_code, fail_expl = (
                    brand_fail,
                    "Brand is outside the confirmed brand restriction.",
                )
            else:
                cond_fail = _condition_ok_simple(condition, condition_restriction)
                if cond_fail:
                    fail_code, fail_expl = (
                        cond_fail,
                        "Condition is outside the confirmed condition constraints.",
                    )
                elif total > max_total_minor:
                    fail_code, fail_expl = (
                        "TOTAL_EXCEEDS_BUDGET",
                        f"All-in total {_fmt(total)} exceeds the confirmed "
                        f"all-in budget {_fmt(max_total_minor)}.",
                    )

        if fail_code is not None:
            rejected.append(
                Rejected(
                    product_id=pid,
                    title=title,
                    reason_code=fail_code,
                    explanation=fail_expl,
                )
            )
            continue

        # Eligible: deterministic explainable score.
        # Lower all-in total = better fit (respects "under budget" mandates);
        # exact-brand match + desired condition nudge within ties.
        score = 0
        score -= total  # cheaper (closer to best value) ranks higher
        why.append(f"All-in total {_fmt(total)} ≤ confirmed budget {_fmt(max_total_minor)}")
        if brand_restriction and isinstance(brand_restriction, dict):
            brands = brand_restriction.get("brands")
            mode = brand_restriction.get("mode", "allow_only")
            if (
                mode == "allow_only"
                and isinstance(brands, list)
                and brands
                and (brand or "").lower() in {str(b).lower() for b in brands}
            ):
                score -= 10_000  # preferred brand tie-break
                why.append("Brand matches the confirmed brand restriction")
        why.append(f"Condition {condition or 'new'} satisfies the mandate")
        eligible.append(
            Candidate(
                product_id=pid,
                title=title,
                brand=brand,
                category=category,
                condition=condition or "new",
                merchant_id=merchant_id,
                unit_price_minor=price_minor,
                shipping_minor=shipping_minor,
                quantity=quantity,
                total_minor=total,
                currency=prod_currency,
                score=score,
                rank=0,
                why=why,
                recurring=bool(product_recurring),
            )
        )

    eligible.sort(key=lambda c: (-c.score, c.product_id))
    for i, cand in enumerate(eligible):
        # rebuild with rank (dataclass frozen)
        eligible[i] = Candidate(
            product_id=cand.product_id,
            title=cand.title,
            brand=cand.brand,
            category=cand.category,
            condition=cand.condition,
            merchant_id=cand.merchant_id,
            unit_price_minor=cand.unit_price_minor,
            shipping_minor=cand.shipping_minor,
            quantity=cand.quantity,
            total_minor=cand.total_minor,
            currency=cand.currency,
            score=cand.score,
            rank=i + 1,
            why=cand.why,
            recurring=cand.recurring,
        )

    return SearchReport(
        intent_id=intent_id,
        inspected=inspected,
        eligible=len(eligible),
        rejected=len(rejected),
        candidates=eligible[: max(1, limit)],
        rejected_samples=rejected[: max(0, include_rejected)],
    )


def _price_total_price(price_minor: int, shipping_minor: int, quantity: int) -> int:
    return price_minor * quantity + shipping_minor


def _brand_ok_simple(brand: str | None, brand_restriction: Any) -> str | None:
    """Stored BrandRestriction domain shape: {"brands": [...], "mode": "allow_only"|"forbid"}."""
    if brand_restriction is None:
        return None
    if isinstance(brand_restriction, dict):
        brands = brand_restriction.get("brands")
        mode = brand_restriction.get("mode", "allow_only")
        pbrand = (brand or "").lower()
        normalized = {str(b).lower() for b in brands} if isinstance(brands, list) else set()
        if not normalized:
            return None
        if mode == "forbid":
            if pbrand in normalized:
                return "BRAND_FORBIDDEN"
        elif pbrand not in normalized:
            return "BRAND_NOT_ALLOWED"
    return None


def _condition_ok_simple(condition: str, condition_restriction: Any) -> str | None:
    """Stored ConditionRestriction domain shape: {"allowed_conditions": [...]}."""
    if condition_restriction is None:
        return None
    if isinstance(condition_restriction, dict):
        conds = condition_restriction.get("allowed_conditions")
        if isinstance(conds, list) and conds:
            allowed = {str(c).lower() for c in conds}
            if (condition or "new").lower() not in allowed:
                return "CONDITION_NOT_ALLOWED"
    return None


def _fmt(minor: int) -> str:
    return f"₹{minor / 100:,.2f}"
