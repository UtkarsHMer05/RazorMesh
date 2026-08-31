"""deep-engine correction G012 transaction baseline snapshots

Revision ID: a1b2c3d4e5f6
Revises: f5a1b2c3d4e5
Create Date: 2026-08-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "f5a1b2c3d4e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "transaction_baselines",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("intent_id", sa.String(length=64), nullable=False),
        sa.Column("checkout_id", sa.String(length=64), nullable=False),
        sa.Column("merchant_id", sa.String(length=64), nullable=False),
        sa.Column("product_id", sa.String(length=64), nullable=False),
        sa.Column("variant_id", sa.String(length=64), nullable=True),
        sa.Column("condition", sa.String(length=32), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price_minor", sa.BigInteger(), nullable=False),
        sa.Column("shipping_minor", sa.BigInteger(), nullable=False),
        sa.Column("fees_minor", sa.BigInteger(), nullable=False),
        sa.Column("tax_minor", sa.BigInteger(), nullable=False),
        sa.Column("total_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("recurring", sa.Boolean(), nullable=False),
        sa.Column("recurring_frequency", sa.String(length=32), nullable=True),
        sa.Column("display_name", sa.String(length=300), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("checkout_id", name="uq_baseline_checkout"),
    )
    op.create_index("ix_baseline_intent_id", "transaction_baselines", ["intent_id"])
    # G019: proposal-time authorization hashes (nullable for legacy rows).
    op.add_column(
        "transaction_baselines",
        sa.Column("expected_checkout_hash", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "transaction_baselines",
        sa.Column("expected_intent_hash", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("transaction_baselines", "expected_intent_hash")
    op.drop_column("transaction_baselines", "expected_checkout_hash")
    op.drop_index("ix_baseline_intent_id", table_name="transaction_baselines")
    op.drop_table("transaction_baselines")