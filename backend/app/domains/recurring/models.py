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
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domains.categories.models import Category
from app.infrastructure.db.base import Base, TimestampMixin


class RecurringExpense(Base, TimestampMixin):
    __tablename__ = "recurring_expenses"
    __table_args__ = (
        CheckConstraint(
            "amount_cents IS NULL OR amount_cents > 0",
            name="amount_positive_or_null",
        ),
        CheckConstraint("scope IN ('personal', 'shared')", name="scope_valid"),
        CheckConstraint(
            "frequency IN ('weekly', 'monthly', 'quarterly', 'semiannual', 'yearly')",
            name="frequency_valid",
        ),
        CheckConstraint("due_day IS NULL OR due_day BETWEEN 1 AND 31", name="due_day_valid"),
        CheckConstraint(
            "end_date IS NULL OR end_date >= start_date",
            name="date_order",
        ),
        CheckConstraint(
            "(scope = 'personal' AND household_id IS NULL) "
            "OR (scope = 'shared' AND household_id IS NOT NULL)",
            name="scope_household_coherent",
        ),
        Index("ix_recurring_expenses_owner_user_id", "owner_user_id"),
        Index("ix_recurring_expenses_household_id", "household_id"),
        Index("ix_recurring_expenses_is_active", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    household_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=True,
    )
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
    )
    allocation_rule_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("allocation_rules.id", ondelete="SET NULL"),
        nullable=True,
    )
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    amount_cents: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    scope: Mapped[str] = mapped_column(String(20), nullable=False)
    frequency: Mapped[str] = mapped_column(String(20), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_day: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    amount_is_variable: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )

    category: Mapped[Category] = relationship()


class RecurringOccurrence(Base, TimestampMixin):
    __tablename__ = "recurring_occurrences"
    __table_args__ = (
        UniqueConstraint("recurring_expense_id", "due_date"),
        UniqueConstraint("transaction_id"),
        CheckConstraint(
            "status IN ('pending', 'confirmed', 'paid', 'skipped')",
            name="status_valid",
        ),
        CheckConstraint(
            "expected_amount_cents IS NULL OR expected_amount_cents > 0",
            name="expected_amount_positive",
        ),
        CheckConstraint(
            "confirmed_amount_cents IS NULL OR confirmed_amount_cents > 0",
            name="confirmed_amount_positive",
        ),
        CheckConstraint(
            "payment_amount_cents IS NULL OR payment_amount_cents > 0",
            name="payment_amount_positive",
        ),
        CheckConstraint(
            "status <> 'paid' OR ("
            "paid_at IS NOT NULL AND payment_amount_cents IS NOT NULL "
            "AND transaction_id IS NOT NULL)",
            name="paid_fields_coherent",
        ),
        Index(
            "ix_recurring_occurrences_recurring_expense_id_due_date",
            "recurring_expense_id",
            "due_date",
        ),
        Index("ix_recurring_occurrences_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    recurring_expense_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recurring_expenses.id", ondelete="CASCADE"),
        nullable=False,
    )
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    expected_amount_cents: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    confirmed_amount_cents: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        server_default=text("'pending'"),
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payment_amount_cents: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    payment_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("transactions.id", ondelete="SET NULL"),
        nullable=True,
    )
