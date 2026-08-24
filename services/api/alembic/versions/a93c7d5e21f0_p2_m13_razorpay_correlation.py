"""P2-M13: razorpay correlation columns + durable provider event inbox

Revision ID: a93c7d5e21f0
Revises: d8b412f091c3
Create Date: 2026-08-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a93c7d5e21f0"
down_revision: str | None = "d8b412f091c3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "execution_attempts",
        sa.Column("provider_name", sa.String(length=32), nullable=False, server_default="mock"),
    )
    op.add_column(
        "execution_attempts",
        sa.Column("razorpay_order_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "execution_attempts",
        sa.Column("razorpay_payment_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "execution_attempts",
        sa.Column("razorpay_order_status", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "execution_attempts",
        sa.Column("razorpay_payment_status", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "execution_attempts",
        sa.Column("callback_verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "execution_attempts",
        sa.Column(
            "fulfilment_state",
            sa.String(length=32),
            nullable=False,
            server_default="NOT_ELIGIBLE",
        ),
    )
    op.add_column(
        "execution_attempts",
        sa.Column("reconcile_state", sa.String(length=32), nullable=False, server_default="NONE"),
    )

    # Identities that must dedup durably (master prompt §24): at most one attempt
    # may claim a given Razorpay order/payment id.
    op.create_index(
        "uq_attempt_razorpay_order",
        "execution_attempts",
        ["razorpay_order_id"],
        unique=True,
        postgresql_where=sa.text("razorpay_order_id IS NOT NULL"),
    )
    op.create_index(
        "uq_attempt_razorpay_payment",
        "execution_attempts",
        ["razorpay_payment_id"],
        unique=True,
        postgresql_where=sa.text("razorpay_payment_id IS NOT NULL"),
    )

    op.create_table(
        "provider_events",
        sa.Column("event_id", sa.String(length=128), primary_key=True),
        sa.Column("provider_name", sa.String(length=32), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified", sa.Boolean(), nullable=False),
        sa.Column(
            "processing_state", sa.String(length=32), nullable=False, server_default="RECEIVED"
        ),
        # SHA-256 of the verified raw body — safe evidence without raw PII payloads
        sa.Column("payload_sha256", sa.String(length=64), nullable=False),
        sa.Column("intent_id", sa.String(length=64), nullable=True),
        sa.Column("razorpay_order_id", sa.String(length=64), nullable=True),
        sa.Column("razorpay_payment_id", sa.String(length=64), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
    )
    op.create_index("ix_provider_events_type", "provider_events", ["event_type"], unique=False)
    op.create_index(
        "ix_provider_events_order", "provider_events", ["razorpay_order_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_provider_events_order", table_name="provider_events")
    op.drop_index("ix_provider_events_type", table_name="provider_events")
    op.drop_table("provider_events")
    op.drop_index("uq_attempt_razorpay_payment", table_name="execution_attempts")
    op.drop_index("uq_attempt_razorpay_order", table_name="execution_attempts")
    op.drop_column("execution_attempts", "reconcile_state")
    op.drop_column("execution_attempts", "fulfilment_state")
    op.drop_column("execution_attempts", "callback_verified_at")
    op.drop_column("execution_attempts", "razorpay_payment_status")
    op.drop_column("execution_attempts", "razorpay_order_status")
    op.drop_column("execution_attempts", "razorpay_payment_id")
    op.drop_column("execution_attempts", "razorpay_order_id")
    op.drop_column("execution_attempts", "provider_name")
