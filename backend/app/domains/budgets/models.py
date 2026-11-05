from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, TimestampMixin


class Budget(Base, TimestampMixin):
    __tablename__ = "budgets"
    __table_args__ = (
        CheckConstraint("budget_type IN ('grocery', 'other')", name="budget_type_valid"),
        CheckConstraint("default_amount_cents >= 0", name="default_amount_non_negative"),
        Index(
            "uq_budgets_household_grocery",
            "household_id",
            unique=True,
            postgresql_where=text("budget_type = 'grocery'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    household_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    budget_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        server_default=text("'other'"),
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
    )
    default_amount_cents: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default=text("0"),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )


class BudgetPeriod(Base):
    __tablename__ = "budget_periods"
    __table_args__ = (
        UniqueConstraint("budget_id", "period_start"),
        CheckConstraint("period_end >= period_start", name="period_order"),
        CheckConstraint("allocated_amount_cents >= 0", name="allocated_non_negative"),
        CheckConstraint("status IN ('open', 'closed')", name="status_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    budget_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("budgets.id", ondelete="CASCADE"),
        nullable=False,
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    allocated_amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'open'"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
