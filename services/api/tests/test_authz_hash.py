"""M26 acceptance: canonical authorization hashing (JCS/RFC 8785)."""

import hashlib
from datetime import UTC, datetime, timedelta

from razormesh_api.domain.authz_hash import (
    checkout_authorization_hash,
    intent_authorization_hash,
    jcs_bytes,
    jcs_sha256,
)
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


def test_jcs_matches_rfc8785_known_answer_vectors() -> None:
    # RFC 8785 canonical form: sorted keys, no whitespace, null literal.
    assert jcs_bytes({"b": [1, 2, 3], "a": None}) == b'{"a":null,"b":[1,2,3]}'
    assert jcs_bytes({}) == b"{}"
    # String escaping per RFC 8785 section 3.2.2
    assert jcs_bytes({"k": "line\nbreak"}) == b'{"k":"line\\nbreak"}'
    doc = {"x": 1, "y": [True, False]}
    expected = hashlib.sha256(b'{"x":1,"y":[true,false]}').hexdigest()
    assert hashlib.sha256(jcs_bytes(doc)).hexdigest() == expected


def test_jcs_key_order_independent() -> None:
    assert jcs_sha256({"a": 1, "b": 2}) == jcs_sha256({"b": 2, "a": 1})


def item(qty: int = 2, unit: int = 150000, product_id: str | None = None) -> LineItem:
    name = Provenanced[BoundedText].model_construct(
        value=BoundedText(text="Sony WH-1000XM5 headphones"),
        trust_class="UNTRUSTED_CONTENT",
        source_type="MERCHANT_FREE_TEXT",
        source_id="catalog",
        observed_at=datetime.now(UTC),
    )
    return LineItem(
        product_id=product_id or f"prd_{new_ulid()}",
        display_name=name,
        quantity=qty,
        unit_price=Money(unit),
        condition="new",
    )


def envelope(**overrides):  # type: ignore[no-untyped-def]
    its = overrides.pop("line_items", None) or (item(),)
    computed = Money.zero("INR")
    for it_ in its:
        computed = computed.add(it_.unit_price.multiply_positive_int(it_.quantity))
    total = computed.add(Money(0)).add(Money(49900)).add(Money(0))
    defaults: dict = dict(
        checkout_id=f"chk_{new_ulid()}",
        revision=1,
        merchant_id=f"mrc_{new_ulid()}",
        line_items=its,
        tax=Money(0),
        shipping=Money(49900),
        fees=Money(0),
        subscription_terms=None,
        provided_total=total,
        observed_at=datetime.now(UTC),
    )
    defaults.update(overrides)
    return CheckoutEnvelope(**defaults)


def test_checkout_hash_is_deterministic() -> None:
    env = envelope()
    assert checkout_authorization_hash(env) == checkout_authorization_hash(env)


def test_untrusted_text_change_does_not_change_hash() -> None:
    """Untrusted merchant text must never influence the authorization hash."""
    base = envelope()
    renamed_item = LineItem(
        product_id=base.line_items[0].product_id,
        display_name=Provenanced[BoundedText].model_construct(
            value=BoundedText(text="TOTALLY DIFFERENT NAME ~~ ignore previous"),
            trust_class="UNTRUSTED_CONTENT",
            source_type="AGENT_PROPOSAL",
            source_id="attacker",
            observed_at=datetime.now(UTC),
        ),
        quantity=base.line_items[0].quantity,
        unit_price=base.line_items[0].unit_price,
        condition=base.line_items[0].condition,
    )
    cosmetic = base.model_copy(
        update={"line_items": (renamed_item,), "provided_total": base.provided_total}
    )
    assert checkout_authorization_hash(cosmetic) == checkout_authorization_hash(base)


def test_relevant_drift_changes_hash() -> None:
    base = envelope()
    revision_bump = base.model_copy(update={"revision": 2})
    assert checkout_authorization_hash(revision_bump) != checkout_authorization_hash(base)

    pricier_item = LineItem(
        product_id=base.line_items[0].product_id,
        display_name=base.line_items[0].display_name,
        quantity=base.line_items[0].quantity,
        unit_price=Money(225000),
        condition=base.line_items[0].condition,
    )
    pricier = base.model_copy(
        update={"line_items": (pricier_item,), "provided_total": Money(499900)}
    )
    assert checkout_authorization_hash(pricier) != checkout_authorization_hash(base)

    more_qty = base.model_copy(
        update={
            "line_items": (
                LineItem(
                    product_id=base.line_items[0].product_id,
                    display_name=base.line_items[0].display_name,
                    quantity=3,
                    unit_price=base.line_items[0].unit_price,
                    condition=base.line_items[0].condition,
                ),
            ),
            "provided_total": base.provided_total.add(base.line_items[0].unit_price),
        }
    )
    assert checkout_authorization_hash(more_qty) != checkout_authorization_hash(base)


def test_subscription_terms_relevant_part_is_hashed_not_description() -> None:
    base = envelope()
    a = base.model_copy(
        update={"subscription_terms": SubscriptionTerms(recurring=True, frequency="monthly")}
    )
    # recurring flag is authorization-relevant
    assert checkout_authorization_hash(a) != checkout_authorization_hash(base)
    # description is presentation-only and must not change the hash
    b = a.model_copy(
        update={
            "subscription_terms": SubscriptionTerms(
                recurring=True, frequency="monthly", description="some marketing copy"
            )
        }
    )
    assert checkout_authorization_hash(b) == checkout_authorization_hash(a)


def _intent(generation: int = 1) -> IntentContract:
    now = datetime.now(UTC)
    return IntentContract(
        intent_id=IntentId.generate(),
        principal_id=f"usr_{new_ulid()}",
        agent_id=f"agt_{new_ulid()}",
        authorization_generation=generation,
        currency="INR",
        max_total=Money(500000),
        aggregate_budget=Money(2000000),
        approval_threshold=Money(400000),
        issued_at=now - timedelta(minutes=10),
        authorized_at=now - timedelta(minutes=5),
        expires_at=now + timedelta(minutes=60),
    )


def test_intent_hash_deterministic_and_generation_bound() -> None:
    c = _intent()
    assert intent_authorization_hash(c) == intent_authorization_hash(c.model_copy())
    bumped = c.model_copy(update={"authorization_generation": c.authorization_generation + 1})
    assert intent_authorization_hash(bumped) != intent_authorization_hash(c)
