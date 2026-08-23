"""M25: evidence ledger ordering anchor (seq) on audit_events.

Revision ID: c5f21a9d3e10
Revises: b31a01dd94f2
Create Date: 2026-08-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c5f21a9d3e10"
down_revision: str | None = "b31a01dd94f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE IF NOT EXISTS audit_events_seq_seq AS bigint")
    op.add_column("audit_events", sa.Column("seq", sa.BigInteger(), nullable=True))
    op.execute(
        """
        WITH ordered AS (
            SELECT event_id, ROW_NUMBER() OVER (ORDER BY created_at, event_id) AS rn
            FROM audit_events
        )
        UPDATE audit_events a SET seq = o.rn
        FROM ordered o WHERE a.event_id = o.event_id
        """
    )
    op.execute(
        "SELECT setval('audit_events_seq_seq', "
        "GREATEST(COALESCE((SELECT MAX(seq) FROM audit_events), 0), 1))"
    )
    op.alter_column(
        "audit_events",
        "seq",
        nullable=False,
        server_default=sa.text("nextval('audit_events_seq_seq')"),
    )
    op.create_unique_constraint("uq_audit_seq", "audit_events", ["seq"])


def downgrade() -> None:
    op.drop_constraint("uq_audit_seq", "audit_events", type_="unique")
    op.drop_column("audit_events", "seq")
    op.execute("DROP SEQUENCE IF EXISTS audit_events_seq_seq")
