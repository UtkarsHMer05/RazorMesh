"""execution integrity constraints

Revision ID: d8b412f091c3
Revises: c5f21a9d3e10
Create Date: 2026-08-24
"""

from collections.abc import Sequence

from alembic import op

revision: str = "d8b412f091c3"
down_revision: str | None = "c5f21a9d3e10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_spend_within_authorized",
        "authorization_spend",
        "reserved_minor + committed_minor <= authorized_minor",
    )
    op.create_unique_constraint("uq_attempt_ticket", "execution_attempts", ["ticket_id"])


def downgrade() -> None:
    op.drop_constraint("uq_attempt_ticket", "execution_attempts", type_="unique")
    op.drop_constraint("ck_spend_within_authorized", "authorization_spend", type_="check")
