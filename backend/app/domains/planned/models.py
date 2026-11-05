from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domains.categories.models import Category
from app.infrastructure.db.base import Base, TimestampMixin


class PlannedExpense(Base, TimestampMixin):
    __tablename__ = "planned_expenses"
    __table_args__ = (
        CheckConstraint("amount_cents > 0", name="amount_positive"),
        CheckConstraint("scope IN ('personal', 'shared')", name="scope_valid"),
        CheckConstraint(
            "status IN ('planned', 'committed', 'paid', 'cancelled')",
            name="status_valid",
        ),
        CheckConstraint(
            "(scope = 'personal' AND household_id IS NULL) "
            "OR (scope = 'shared' AND household_id IS NOT NULL)",
            name="scope_household_coherent",
        ),
        UniqueConstraint("transaction_id"),
        Index(
            "ix_planned_expenses_user_id_planned_date",
            "user_id",
            "planned_date",
        ),
        Index(
            "ix_planned_expenses_household_id_planned_date",
            "household_id",
            "planned_date",
        ),
        Index("ix_planned_expenses_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    household_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
    )
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    scope: Mapped[str] = mapped_column(String(20), nullable=False)
    planned_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'planned'"),
    )
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("transactions.id", ondelete="SET NULL"),
        nullable=True,
    )

    category: Mapped[Category] = relationship()
