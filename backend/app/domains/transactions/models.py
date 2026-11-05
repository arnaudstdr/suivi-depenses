from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domains.categories.models import Category
from app.infrastructure.db.base import Base, TimestampMixin


class Transaction(Base, TimestampMixin):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("amount_cents > 0", name="amount_positive"),
        CheckConstraint(
            "transaction_type IN ('expense', 'refund')",
            name="transaction_type_valid",
        ),
        CheckConstraint("scope IN ('personal', 'shared')", name="scope_valid"),
        CheckConstraint("status = 'paid'", name="status_paid"),
        CheckConstraint(
            "(scope = 'personal' AND household_id IS NULL) "
            "OR (scope = 'shared' AND household_id IS NOT NULL)",
            name="scope_household_coherent",
        ),
        CheckConstraint(
            "(transaction_type = 'expense' AND original_transaction_id IS NULL) "
            "OR (transaction_type = 'refund' AND original_transaction_id IS NOT NULL)",
            name="refund_link_coherent",
        ),
        CheckConstraint(
            "budget_id IS NULL OR scope = 'shared'",
            name="budget_requires_shared",
        ),
        Index(
            "ix_transactions_user_id_transaction_date",
            "user_id",
            "transaction_date",
        ),
        Index(
            "ix_transactions_household_id_transaction_date",
            "household_id",
            "transaction_date",
        ),
        Index("ix_transactions_category_id", "category_id"),
        Index("ix_transactions_budget_id", "budget_id"),
        Index("ix_transactions_original_transaction_id", "original_transaction_id"),
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
    transaction_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'expense'"),
    )
    scope: Mapped[str] = mapped_column(String(20), nullable=False)
    budget_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("budgets.id", ondelete="SET NULL"),
        nullable=True,
    )
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'paid'"),
    )
    original_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("transactions.id", ondelete="SET NULL"),
        nullable=True,
    )
    recurring_occurrence_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(
            "recurring_occurrences.id",
            ondelete="SET NULL",
            use_alter=True,
        ),
        nullable=True,
        unique=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    category: Mapped[Category] = relationship()
