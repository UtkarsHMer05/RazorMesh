"""P2-M13: Razorpay correlation schema — durable dedup identities.

Proves at the DB level:
1. At most one execution attempt may claim a given Razorpay order id
   (partial unique index; P2-S22 correlation + master prompt §24).
2. The provider event inbox enforces x-razorpay-event-id uniqueness durably
   (P2-S12): duplicate delivery cannot create two rows.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from razormesh_api.domain.authz_hash import checkout_authorization_hash
from razormesh_api.domain.checkout import BoundedText, CheckoutEnvelope, LineItem
from razormesh_api.domain.ids import DecisionId, ExecutionTicketId, IntentId, new_ulid
from razormesh_api.domain.intent import IntentContract
from razormesh_api.domain.money import Money
from razormesh_api.domain.provenance import Provenanced
from razormesh_api.persistence.db import create_db_engine, create_session_factory
from razormesh_api.persistence.models import (
    AuthorizationSpend,
    Checkout,
    Decision,
    ExecutionAttempt,
    ExecutionTicket,
    Merchant,
    ProviderEvent,
)
from razormesh_api.persistence.models import (
    IntentContract as RowIntent,
)
from razormesh_api.settings import get_settings

NOW = datetime.now(UTC)


@pytest.fixture()
def db_session_factory():  # type: ignore[no-untyped-def]
    engine = create_db_engine(get_settings().database_url)
    factory = create_session_factory(engine)
    yield factory
    with factory() as s, s.begin():
        s.query(ExecutionAttempt).delete()
        s.query(ExecutionTicket).delete()
        s.query(Decision).delete()
        s.query(Checkout).delete()
        s.query(AuthorizationSpend).delete()
        s.query(Merchant).delete()
        s.query(RowIntent).delete()


def _seed_authorization_chain(chain_factory, tag: str) -> tuple[str, str]:
    """Persist intent+checkout+decision+ticket chain; return (intent_id, ticket_id)."""
    now = datetime.now(UTC)
    item = LineItem(
        product_id=f"prd_{new_ulid()}",
        display_name=Provenanced[BoundedText].model_construct(
            value=BoundedText(text="Schema item"),
            trust_class="UNTRUSTED_CONTENT",
            source_type="MERCHANT_FREE_TEXT",
            source_id="c",
            observed_at=NOW,
        ),
        quantity=1,
        unit_price=Money(100000),
    )
    env = CheckoutEnvelope(
        checkout_id=f"chk_{new_ulid()}",
        revision=1,
        merchant_id=f"mrc_{new_ulid()}",
        line_items=(item,),
        tax=Money(0),
        shipping=Money(0),
        fees=Money(0),
        provided_total=Money(100000),
        observed_at=NOW,
    )
    total = 100000
    decision_id = DecisionId.generate()
    intent = IntentContract(
        intent_id=IntentId.generate(),
        principal_id=f"usr_{new_ulid()}",
        agent_id=f"agt_{new_ulid()}",
        authorization_generation=1,
        currency="INR",
        max_total=Money(500000),
        aggregate_budget=Money(5000000),
        approval_threshold=Money(400000),
        issued_at=NOW,
        authorized_at=NOW,
        expires_at=NOW + timedelta(minutes=30),
    )
    ticket_id = str(ExecutionTicketId.generate())

    with chain_factory() as s, s.begin():
        s.merge(
            Merchant(
                id=str(env.merchant_id),
                name=f"Schema Merchant {tag}",
                display_name="Schema Merchant",
                created_at=now,
                updated_at=now,
            )
        )
        s.flush()
        s.merge(
            RowIntent(
                intent_id=str(intent.intent_id),
                principal_id=str(intent.principal_id),
                agent_id=str(intent.agent_id),
                authorization_generation=1,
                status="AUTHORIZED",
                currency="INR",
                max_total_minor=500000,
                aggregate_budget_minor=5000000,
                max_quantity=intent.max_quantity,
                recurring_allowed=False,
                approval_threshold_minor=400000,
                issued_at=NOW,
                authorized_at=NOW,
                expires_at=NOW + timedelta(minutes=30),
                created_at=now,
                updated_at=now,
            )
        )
        s.flush()
        s.merge(
            Checkout(
                checkout_id=str(env.checkout_id),
                revision=env.revision,
                merchant_id=str(env.merchant_id),
                line_items=[
                    {
                        "product_id": str(i.product_id),
                        "quantity": i.quantity,
                        "unit_price_minor": i.unit_price.amount_minor,
                        "currency": i.unit_price.currency,
                        "condition": i.condition,
                    }
                    for i in env.line_items
                ],
                tax_minor=env.tax.amount_minor,
                shipping_minor=env.shipping.amount_minor,
                fees_minor=env.fees.amount_minor,
                provided_total_minor=total,
                computed_total_minor=total,
                currency="INR",
                observed_at=now,
                created_at=now,
            )
        )
        s.flush()
        s.merge(
            Decision(
                decision_id=str(decision_id),
                intent_id=str(intent.intent_id),
                checkout_id=str(env.checkout_id),
                intent_generation=1,
                checkout_hash=checkout_authorization_hash(env),
                policy_version="razormesh-phase1-policy-v1",
                decision="ALLOW",
                created_at=now,
            )
        )
        s.flush()
        s.merge(
            ExecutionTicket(
                ticket_id=ticket_id,
                principal_id=str(intent.principal_id),
                agent_id=str(intent.agent_id),
                intent_id=str(intent.intent_id),
                intent_hash=f"ihash-{tag}",
                authorization_generation=1,
                checkout_hash=checkout_authorization_hash(env),
                checkout_revision=1,
                merchant_id=str(env.merchant_id),
                amount_minor=total,
                currency="INR",
                decision_id=str(decision_id),
                policy_version="razormesh-phase1-policy-v1",
                nonce=f"nonce-schema-{tag}",
                issued_at=now,
                expires_at=now + timedelta(minutes=5),
                used_at=None,
                created_at=now,
            )
        )
        s.flush()

    return str(intent.intent_id), ticket_id


def test_attempt_claims_razorpay_order_id_exactly_once(db_session_factory) -> None:  # type: ignore[no-untyped-def]
    intent_a, ticket_a = _seed_authorization_chain(db_session_factory, "a")
    intent_b, ticket_b = _seed_authorization_chain(db_session_factory, "b")
    now = datetime.now(UTC)

    def attempt(attempt_id: str, ticket_id: str, intent_id: str) -> ExecutionAttempt:
        return ExecutionAttempt(
            execution_attempt_id=attempt_id,
            idempotency_key=f"idem-{attempt_id}",
            ticket_id=ticket_id,
            intent_id=intent_id,
            checkout_id=f"chk_{new_ulid()}",
            amount_minor=100000,
            currency="INR",
            state="CREATED",
            provider_name="razorpay",
            razorpay_order_id="order_schema_dup",
            created_at=now,
            updated_at=now,
        )

    with db_session_factory() as s, s.begin():
        s.add(attempt("exa_schema_a", ticket_a, intent_a))
        s.flush()  # first claim succeeds

    with db_session_factory() as s, s.begin():
        s.add(attempt("exa_schema_b", ticket_b, intent_b))
        with pytest.raises(IntegrityError):
            s.flush()
        s.rollback()

    with db_session_factory() as s, s.begin():
        rows = s.execute(select(ExecutionAttempt)).scalars().all()
    assert [r.execution_attempt_id for r in rows] == ["exa_schema_a"]


def test_provider_event_id_dedups_durably(db_session_factory) -> None:  # type: ignore[no-untyped-def]
    now = datetime.now(UTC)
    base = dict(
        provider_name="razorpay",
        event_type="payment.captured",
        received_at=now,
        verified=True,
        processing_state="PROCESSED",
        payload_sha256="a" * 64,
    )
    with db_session_factory() as s, s.begin():
        s.add(ProviderEvent(event_id="evt_dup_test", **base))
        s.flush()
        s.add(ProviderEvent(event_id="evt_dup_test", **base))
        with pytest.raises(IntegrityError):
            s.flush()
        s.rollback()

    with db_session_factory() as s, s.begin():
        stored = (
            s.execute(select(ProviderEvent).where(ProviderEvent.event_id == "evt_dup_test"))
            .scalars()
            .all()
        )
    # the transaction containing BOTH inserts was rolled back after the violation
    assert stored == []
