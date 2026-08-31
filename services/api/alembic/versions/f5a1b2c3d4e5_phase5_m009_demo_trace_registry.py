"""phase5-m009 demo trace registry

Revision ID: f5a1b2c3d4e5
Revises: e7a1c4f9b2d5
Create Date: 2026-08-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f5a1b2c3d4e5"
down_revision: str | None = "e7a1c4f9b2d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "demo_traces",
        sa.Column("trace_id", sa.String(length=16), primary_key=True),
        sa.Column("intent_id", sa.String(length=64), nullable=False),
        sa.Column("draft_id", sa.String(length=64), nullable=True),
        sa.Column("checkout_id", sa.String(length=64), nullable=True),
        sa.Column("run_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("intent_id", name="uq_demo_trace_intent"),
    )
    op.create_index("ix_demo_traces_updated_at", "demo_traces", ["updated_at"])


def downgrade() -> None:
    op.drop_index("ix_demo_traces_updated_at", table_name="demo_traces")
    op.drop_table("demo_traces")
