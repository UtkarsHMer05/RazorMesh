from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from razormesh_api.persistence.base import Base


class Merchant(Base):
    __tablename__ = "merchants"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        Index("ix_products_merchant_id", "merchant_id"),
        Index("ix_products_category", "category"),
        Index("ix_products_brand", "brand"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    brand: Mapped[str | None] = mapped_column(String(100), nullable=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    condition: Mapped[str] = mapped_column(String(32), nullable=False, default="new")
    price_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="INR")
    shipping_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    tax_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    fees_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    recurring: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    recurring_frequency: Mapped[str | None] = mapped_column(String(32), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class IntentContract(Base):
    __tablename__ = "intent_contracts"

    intent_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    principal_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    authorization_generation: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="AUTHORIZED")
    allowed_merchant_ids: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
    allowed_product_ids: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
    allowed_categories: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
    brand_restriction: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    condition_restriction: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    max_total_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    aggregate_budget_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    max_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    recurring_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    approval_threshold_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    authorized_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Checkout(Base):
    __tablename__ = "checkouts"
    __table_args__ = (Index("ix_checkouts_merchant_id", "merchant_id"),)

    checkout_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    merchant_id: Mapped[str] = mapped_column(String(64), ForeignKey("merchants.id"), nullable=False)
    line_items: Mapped[dict | list] = mapped_column(JSONB, nullable=False)
    tax_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    shipping_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    fees_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    provided_total_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    computed_total_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    subscription_terms: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Decision(Base):
    __tablename__ = "decisions"
    __table_args__ = (
        Index("ix_decisions_intent_id", "intent_id"),
        Index("ix_decisions_checkout_hash", "checkout_hash"),
    )

    decision_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    intent_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("intent_contracts.intent_id"), nullable=False
    )
    checkout_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("checkouts.checkout_id"), nullable=False
    )
    intent_generation: Mapped[int] = mapped_column(Integer, nullable=False)
    checkout_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    decision: Mapped[str] = mapped_column(String(16), nullable=False)
    reason_codes: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
    rule_results: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AuthorizationSpend(Base):
    __tablename__ = "authorization_spend"
    __table_args__ = (
        CheckConstraint("reserved_minor >= 0", name="ck_spend_reserved_nonneg"),
        CheckConstraint("committed_minor >= 0", name="ck_spend_committed_nonneg"),
        CheckConstraint("authorized_minor >= 0", name="ck_spend_authorized_nonneg"),
    )

    intent_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("intent_contracts.intent_id", ondelete="CASCADE"), primary_key=True
    )
    authorized_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reserved_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    committed_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ExecutionTicket(Base):
    __tablename__ = "execution_tickets"
    __table_args__ = (
        UniqueConstraint("nonce", name="uq_ticket_nonce"),
        Index("ix_tickets_intent_id", "intent_id"),
        Index("ix_tickets_principal_id", "principal_id"),
    )

    ticket_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    principal_id: Mapped[str] = mapped_column(String(64), nullable=False)
    agent_id: Mapped[str] = mapped_column(String(64), nullable=False)
    intent_id: Mapped[str] = mapped_column(String(64), nullable=False)
    intent_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    authorization_generation: Mapped[int] = mapped_column(Integer, nullable=False)
    checkout_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    checkout_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    merchant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    decision_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("decisions.decision_id"), nullable=False
    )
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    nonce: Mapped[str] = mapped_column(String(128), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ExecutionAttempt(Base):
    __tablename__ = "execution_attempts"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_attempt_idempotency"),
        Index("ix_attempts_ticket_id", "ticket_id"),
        Index("ix_attempts_intent_id", "intent_id"),
        Index("ix_attempts_state", "state"),
    )

    execution_attempt_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    ticket_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("execution_tickets.ticket_id"), nullable=False
    )
    intent_id: Mapped[str] = mapped_column(String(64), nullable=False)
    checkout_id: Mapped[str] = mapped_column(String(64), nullable=False)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="CREATED")
    provider_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    provider_event: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        UniqueConstraint("current_event_hash", name="uq_audit_current_hash"),
        UniqueConstraint("seq", name="uq_audit_seq"),
        Index("ix_audit_timestamp", "timestamp"),
        Index("ix_audit_intent_id", "intent_id"),
    )

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    seq: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        unique=True,
        server_default=text("nextval('audit_events_seq_seq')"),
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    actor: Mapped[str] = mapped_column(String(64), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    intent_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    checkout_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    decision_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ticket_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    intent_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    checkout_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reason_codes: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
    previous_event_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    current_event_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
