"""M29 acceptance: merchant/product/category/brand/quantity rules + unknown data."""

from datetime import UTC, datetime, timedelta

from razormesh_api.domain.checkout import BoundedText, CheckoutEnvelope, LineItem
from razormesh_api.domain.ids import IntentId, new_ulid
from razormesh_api.domain.intent import BrandRestriction, IntentContract
from razormesh_api.domain.money import Money
from razormesh_api.domain.provenance import Provenanced
from razormesh_api.rules.catalog_rules import (
    CATALOG_RULES,
    brand_restriction_rule,
    category_rule,
    merchant_allowlist_rule,
    product_allowlist_rule,
    quantity_rule,
)
from razormesh_api.rules.engine import (
    EvaluationContext,
    ProductFacts,
    RuleOutcome,
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


def _intent(**overrides):  # type: ignore[no-untyped-def]
    now = datetime.now(UTC)
    defaults: dict = dict(
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
    defaults.update(overrides)
    return IntentContract(**defaults)


def _ctx(items=None, intent=None, facts=None):  # type: ignore[no-untyped-def]
    its = items or (_item(),)
    computed = Money.zero("INR")
    for it_ in its:
        computed = computed.add(it_.unit_price.multiply_positive_int(it_.quantity))
    env = CheckoutEnvelope(
        checkout_id=f"chk_{new_ulid()}",
        revision=1,
        merchant_id=f"mrc_{new_ulid()}",
        line_items=its,
        tax=Money(0),
        shipping=Money(0),
        fees=Money(0),
        provided_total=computed,
        observed_at=datetime.now(UTC),
    )
    return EvaluationContext(intent=intent or _intent(), checkout=env, product_facts=facts)


def test_merchant_allowlist_none_any_empty_nothing() -> None:
    # None -> any merchant passes
    ctx = _ctx()
    assert merchant_allowlist_rule.evaluate(ctx).outcome == RuleOutcome.PASS

    # empty set -> nothing is allowed (fail-closed semantics of SEC-018)
    empty_intent = _intent(allowed_merchant_ids=frozenset())
    res = merchant_allowlist_rule.evaluate(
        EvaluationContext(intent=empty_intent, checkout=ctx.checkout)
    )
    assert res.outcome == RuleOutcome.FAIL
    assert "MERCHANT_NOT_ALLOWED" in res.reason_codes


def test_merchant_membership_decides() -> None:
    ctx = _ctx()
    m = ctx.checkout.merchant_id
    allow_intent = _intent(allowed_merchant_ids=frozenset({m}))
    assert (
        merchant_allowlist_rule.evaluate(
            EvaluationContext(intent=allow_intent, checkout=ctx.checkout)
        ).outcome
        == RuleOutcome.PASS
    )

    other = type(m).generate()
    deny_intent = _intent(allowed_merchant_ids=frozenset({other}))
    res = merchant_allowlist_rule.evaluate(
        EvaluationContext(intent=deny_intent, checkout=ctx.checkout)
    )
    assert res.outcome == RuleOutcome.FAIL


def test_product_allowlist_and_membership() -> None:
    ctx = _ctx()
    pid = ctx.checkout.line_items[0].product_id
    allow = _intent(allowed_product_ids=frozenset({pid}))
    assert (
        product_allowlist_rule.evaluate(
            EvaluationContext(intent=allow, checkout=ctx.checkout)
        ).outcome
        == RuleOutcome.PASS
    )

    forbid_all = _intent(allowed_product_ids=frozenset())
    res = product_allowlist_rule.evaluate(
        EvaluationContext(intent=forbid_all, checkout=ctx.checkout)
    )
    assert res.outcome == RuleOutcome.FAIL
    assert "PRODUCT_NOT_ALLOWED" in res.reason_codes


def test_category_unknown_fact_is_unknown_not_pass() -> None:
    base = _ctx()
    audio_intent = _intent(allowed_categories=frozenset({"audio"}))
    pid = base.checkout.line_items[0].product_id.value

    # no facts at all -> UNKNOWN (fail-closed), never PASS
    res = category_rule.evaluate(EvaluationContext(intent=audio_intent, checkout=base.checkout))
    assert res.outcome == RuleOutcome.UNKNOWN
    assert "CATEGORY_UNKNOWN" in res.reason_codes

    # trusted fact says 'books' -> disallowed FAIL
    res2 = category_rule.evaluate(
        EvaluationContext(
            intent=audio_intent,
            checkout=base.checkout,
            product_facts={pid: ProductFacts(category="books")},
        )
    )
    assert res2.outcome == RuleOutcome.FAIL
    assert "CATEGORY_NOT_ALLOWED" in res2.reason_codes

    # trusted fact matches -> PASS
    res3 = category_rule.evaluate(
        EvaluationContext(
            intent=audio_intent,
            checkout=base.checkout,
            product_facts={pid: ProductFacts(category="audio")},
        )
    )
    assert res3.outcome == RuleOutcome.PASS


def test_brand_restriction_modes_and_unknown() -> None:
    base = _ctx()
    pid = base.checkout.line_items[0].product_id.value
    restriction = BrandRestriction(brands=frozenset({"Sony"}), mode="allow_only")
    base_intent = _intent(brand_restriction=restriction)

    # no fact -> UNKNOWN
    nofact = brand_restriction_rule.evaluate(
        EvaluationContext(intent=base_intent, checkout=base.checkout)
    )
    assert nofact.outcome == RuleOutcome.UNKNOWN

    # brand matches (case-insensitive) -> PASS
    ok = brand_restriction_rule.evaluate(
        EvaluationContext(
            intent=base_intent,
            checkout=base.checkout,
            product_facts={pid: ProductFacts(brand="SONY")},
        )
    )
    assert ok.outcome == RuleOutcome.PASS

    # different brand -> FAIL
    bad = brand_restriction_rule.evaluate(
        EvaluationContext(
            intent=base_intent,
            checkout=base.checkout,
            product_facts={pid: ProductFacts(brand="Bose")},
        )
    )
    assert bad.outcome == RuleOutcome.FAIL
    assert "BRAND_RESTRICTION_VIOLATED" in bad.reason_codes

    # forbid mode: other brand passes, forbidden brand fails
    forbid_intent = _intent(
        brand_restriction=BrandRestriction(brands=frozenset({"Bose"}), mode="forbid")
    )
    assert (
        brand_restriction_rule.evaluate(
            EvaluationContext(
                intent=forbid_intent,
                checkout=base.checkout,
                product_facts={pid: ProductFacts(brand="Sony")},
            )
        ).outcome
        == RuleOutcome.PASS
    )
    blocked = brand_restriction_rule.evaluate(
        EvaluationContext(
            intent=forbid_intent,
            checkout=base.checkout,
            product_facts={pid: ProductFacts(brand="Bose")},
        )
    )
    assert blocked.outcome == RuleOutcome.FAIL


def test_quantity_rules_per_line_and_aggregate() -> None:
    # max_quantity default 1; qty 1 passes
    assert quantity_rule.evaluate(_ctx()).outcome == RuleOutcome.PASS

    # qty 2 on a single line exceeds max_quantity 1
    over = _ctx(items=(_item(qty=2),))
    res = quantity_rule.evaluate(over)
    assert res.outcome == RuleOutcome.FAIL
    assert "QUANTITY_EXCEEDS_MAX" in res.reason_codes

    # max_quantity 3 allows qty-3 lines
    loose = _intent(max_quantity=3)
    assert (
        quantity_rule.evaluate(_ctx(items=(_item(qty=3),), intent=loose)).outcome
        == RuleOutcome.PASS
    )


def test_catalog_registry_deterministic_clean_pass() -> None:
    ids = [r.rule_id for r in CATALOG_RULES]
    assert len(set(ids)) == len(ids)
    ctx = _ctx(facts={"x": ProductFacts(brand="B", category="c")})
    report_outcomes = [r.evaluate(ctx).outcome for r in CATALOG_RULES]
    assert report_outcomes == [RuleOutcome.PASS] * len(CATALOG_RULES)
