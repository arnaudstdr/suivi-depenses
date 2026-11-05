"""imports and notifications

Revision ID: 0007_imports_notifications
Revises: 0006_occurrence_history
Create Date: 2026-11-05 15:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_imports_notifications"
down_revision: str | Sequence[str] | None = "0006_occurrence_history"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "import_batches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "target_type",
            sa.String(length=30),
            server_default=sa.text("'transactions'"),
            nullable=False,
        ),
        sa.Column("scope", sa.String(length=20), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column("source_format", sa.String(length=10), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=True),
        sa.Column("checksum", sa.String(length=64), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'preview'"),
            nullable=False,
        ),
        sa.Column("total_rows", sa.SmallInteger(), nullable=False),
        sa.Column("valid_rows", sa.SmallInteger(), nullable=False),
        sa.Column("duplicate_rows", sa.SmallInteger(), nullable=False),
        sa.Column("error_rows", sa.SmallInteger(), nullable=False),
        sa.Column("preview", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('preview', 'validated', 'cancelled')",
            name=op.f("ck_import_batches_status_valid"),
        ),
        sa.CheckConstraint(
            "scope IN ('personal', 'shared')",
            name=op.f("ck_import_batches_scope_valid"),
        ),
        sa.CheckConstraint(
            "target_type IN ('transactions')",
            name=op.f("ck_import_batches_target_type_valid"),
        ),
        sa.CheckConstraint(
            "total_rows >= 0", name=op.f("ck_import_batches_total_rows_non_negative")
        ),
        sa.CheckConstraint(
            "valid_rows >= 0", name=op.f("ck_import_batches_valid_rows_non_negative")
        ),
        sa.CheckConstraint(
            "duplicate_rows >= 0",
            name=op.f("ck_import_batches_duplicate_rows_non_negative"),
        ),
        sa.CheckConstraint(
            "error_rows >= 0", name=op.f("ck_import_batches_error_rows_non_negative")
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_import_batches_created_by_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households.id"],
            name=op.f("fk_import_batches_household_id_households"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_import_batches")),
    )
    op.create_index(
        "ix_import_batches_household_id_created_at",
        "import_batches",
        ["household_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_import_batches_created_by_user_id_created_at",
        "import_batches",
        ["created_by_user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_import_batches_status",
        "import_batches",
        ["status"],
        unique=False,
    )

    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=True),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("entity_type", sa.String(length=50), nullable=True),
        sa.Column("entity_id", sa.Uuid(), nullable=True),
        sa.Column("dedupe_key", sa.String(length=200), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "char_length(trim(type)) > 0",
            name=op.f("ck_notifications_type_not_blank"),
        ),
        sa.CheckConstraint(
            "char_length(trim(title)) > 0",
            name=op.f("ck_notifications_title_not_blank"),
        ),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households.id"],
            name=op.f("fk_notifications_household_id_households"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_notifications_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notifications")),
        sa.UniqueConstraint(
            "user_id",
            "dedupe_key",
            name=op.f("uq_notifications_user_id_dedupe_key"),
        ),
    )
    op.create_index(
        "ix_notifications_user_id_created_at",
        "notifications",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_notifications_user_id_read_at",
        "notifications",
        ["user_id", "read_at"],
        unique=False,
    )

    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column(
            "in_app_enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "push_enabled",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "char_length(trim(type)) > 0",
            name=op.f("ck_notification_preferences_type_not_blank"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_notification_preferences_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notification_preferences")),
        sa.UniqueConstraint(
            "user_id",
            "type",
            name=op.f("uq_notification_preferences_user_id_type"),
        ),
    )


def downgrade() -> None:
    op.drop_table("notification_preferences")
    op.drop_index("ix_notifications_user_id_read_at", table_name="notifications")
    op.drop_index("ix_notifications_user_id_created_at", table_name="notifications")
    op.drop_table("notifications")
    op.drop_index("ix_import_batches_status", table_name="import_batches")
    op.drop_index(
        "ix_import_batches_created_by_user_id_created_at",
        table_name="import_batches",
    )
    op.drop_index(
        "ix_import_batches_household_id_created_at",
        table_name="import_batches",
    )
    op.drop_table("import_batches")
