from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, TimestampMixin


class ImportBatch(Base, TimestampMixin):
    __tablename__ = "import_batches"
    __table_args__ = (
        CheckConstraint(
            "status IN ('preview', 'validated', 'cancelled')",
            name="status_valid",
        ),
        CheckConstraint("scope IN ('personal', 'shared')", name="scope_valid"),
        CheckConstraint(
            "target_type IN ('transactions')",
            name="target_type_valid",
        ),
        CheckConstraint("total_rows >= 0", name="total_rows_non_negative"),
        CheckConstraint("valid_rows >= 0", name="valid_rows_non_negative"),
        CheckConstraint("duplicate_rows >= 0", name="duplicate_rows_non_negative"),
        CheckConstraint("error_rows >= 0", name="error_rows_non_negative"),
        Index(
            "ix_import_batches_household_id_created_at",
            "household_id",
            "created_at",
        ),
        Index(
            "ix_import_batches_created_by_user_id_created_at",
            "created_by_user_id",
            "created_at",
        ),
        Index("ix_import_batches_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    household_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        server_default=text("'transactions'"),
    )
    scope: Mapped[str] = mapped_column(String(20), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_format: Mapped[str] = mapped_column(String(10), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'preview'"),
    )
    total_rows: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    valid_rows: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    duplicate_rows: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    error_rows: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    preview: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    validated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
