"""p3-m16 intent drafts (human confirmation state)

Revision ID: e7a1c4f9b2d5
Revises: a93c7d5e21f0
Create Date: 2026-08-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e7a1c4f9b2d5"
down_revision: str | None = "a93c7d5e21f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "intent_drafts",
        sa.Column("draft_id", sa.String(length=64), primary_key=True),
        sa.Column("principal_id", sa.String(length=64), nullable=False),
        sa.Column("agent_id", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("schema_version", sa.String(length=32), nullable=False),
        sa.Column("source_text_sha256", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("compiler_model", sa.String(length=64), nullable=False),
        sa.Column("prompt_version", sa.String(length=64), nullable=False),
        sa.Column("prompt_sha256", sa.String(length=64), nullable=False),
        sa.Column("compile_attempts", sa.Integer(), nullable=False),
        sa.Column(
            "request_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("superseded_by", sa.String(length=64), nullable=True),
        sa.Column("confirmation_nonce", sa.String(length=128), nullable=True),
        sa.Column("confirmed_generation", sa.Integer(), nullable=True),
        sa.Column("intent_id", sa.String(length=64), nullable=True),
        sa.Column("actor", sa.String(length=64), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "state IN ('DRAFT','NEEDS_CLARIFICATION','CONFIRMED','REJECTED')",
            name="ck_intent_draft_state",
        ),
        sa.UniqueConstraint("confirmation_nonce", name="uq_draft_confirmation_nonce"),
    )
    op.create_index(
        "ix_intent_drafts_principal_agent",
        "intent_drafts",
        ["principal_id", "agent_id"],
    )
    op.create_index("ix_intent_drafts_state", "intent_drafts", ["state"])


def downgrade() -> None:
    op.drop_index("ix_intent_drafts_state", table_name="intent_drafts")
    op.drop_index("ix_intent_drafts_principal_agent", table_name="intent_drafts")
    op.drop_table("intent_drafts")
