from __future__ import annotations

import uuid

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (
        CheckConstraint("category_type = 'expense'", name="category_type_expense"),
        Index("ix_categories_household_id", "household_id"),
        Index(
            "uq_categories_global_name",
            text("lower(name)"),
            unique=True,
            postgresql_where=text("household_id IS NULL"),
        ),
        Index(
            "uq_categories_household_name",
            "household_id",
            text("lower(name)"),
            unique=True,
            postgresql_where=text("household_id IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    household_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    category_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'expense'"),
    )
    is_grocery: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )
