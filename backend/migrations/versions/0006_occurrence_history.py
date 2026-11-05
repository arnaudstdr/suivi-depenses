"""occurrence confirmation, skip and audit history

Revision ID: 0006_occurrence_history
Revises: 0005_allocations
Create Date: 2026-11-05 14:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_occurrence_history"
down_revision: str | Sequence[str] | None = "0005_allocations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "recurring_occurrences",
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "recurring_occurrences",
        sa.Column("skipped_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "recurring_occurrences",
        sa.Column("skip_reason", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_audit_logs_entity_type_entity_id_occurred_at",
        "audit_logs",
        ["entity_type", "entity_id", "occurred_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_audit_logs_entity_type_entity_id_occurred_at",
        table_name="audit_logs",
    )
    op.drop_column("recurring_occurrences", "skip_reason")
    op.drop_column("recurring_occurrences", "skipped_at")
    op.drop_column("recurring_occurrences", "confirmed_at")
