from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.domains.users.models import User


class AllocationRule(Base, TimestampMixin):
    __tablename__ = "allocation_rules"
    __table_args__ = (
        Index(
            "uq_allocation_rules_household_default",
            "household_id",
            unique=True,
            postgresql_where=text("is_default"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    household_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    is_default: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )

    members: Mapped[list[AllocationRuleMember]] = relationship(
        back_populates="rule",
        cascade="all, delete-orphan",
    )


class AllocationRuleMember(Base):
    __tablename__ = "allocation_rule_members"
    __table_args__ = (
        UniqueConstraint("allocation_rule_id", "user_id"),
        CheckConstraint(
            "percentage >= 0 AND percentage <= 100",
            name="percentage_range",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    allocation_rule_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("allocation_rules.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    percentage: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)

    rule: Mapped[AllocationRule] = relationship(back_populates="members")
    user: Mapped[User] = relationship()


class HouseholdContribution(Base, TimestampMixin):
    __tablename__ = "household_contributions"
    __table_args__ = (
        UniqueConstraint("household_id", "user_id", "period_start"),
        UniqueConstraint("transaction_id"),
        CheckConstraint("amount_cents >= 0", name="amount_non_negative"),
        CheckConstraint(
            "transferred_amount_cents IS NULL OR transferred_amount_cents > 0",
            name="transferred_amount_positive",
        ),
        CheckConstraint(
            "status IN ('pending', 'transferred', 'cancelled')",
            name="status_valid",
        ),
        CheckConstraint(
            "status <> 'transferred' OR ("
            "transferred_at IS NOT NULL AND transferred_amount_cents IS NOT NULL "
            "AND transaction_id IS NOT NULL)",
            name="transferred_fields_coherent",
        ),
        CheckConstraint(
            "allocation_percentage >= 0 AND allocation_percentage <= 100",
            name="allocation_percentage_range",
        ),
        Index(
            "ix_household_contributions_household_id_period_start",
            "household_id",
            "period_start",
        ),
        Index(
            "ix_household_contributions_user_id_period_start",
            "user_id",
            "period_start",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    household_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    allocation_percentage: Mapped[Decimal] = mapped_column(
        Numeric(6, 3),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'pending'"),
    )
    transferred_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    transferred_amount_cents: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("transactions.id", ondelete="SET NULL"),
        nullable=True,
    )

    user: Mapped[User] = relationship()
