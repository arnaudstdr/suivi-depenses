import uuid
from datetime import date, datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.domains.allocations.models import HouseholdContribution
from app.domains.planned.models import PlannedExpense
from app.domains.recurring.models import RecurringExpense, RecurringOccurrence
from app.domains.transactions.models import Transaction


class DashboardRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def personal_recurring(
        self,
        user_id: uuid.UUID,
        start: date,
        end: date,
        start_at: datetime,
        end_at: datetime,
    ) -> list[tuple[RecurringOccurrence, RecurringExpense]]:
        return list(
            self._db.execute(
                select(RecurringOccurrence, RecurringExpense)
                .join(
                    RecurringExpense,
                    RecurringOccurrence.recurring_expense_id == RecurringExpense.id,
                )
                .where(
                    RecurringExpense.scope == "personal",
                    RecurringExpense.owner_user_id == user_id,
                    or_(
                        and_(
                            RecurringOccurrence.status.in_(["pending", "confirmed"]),
                            RecurringOccurrence.due_date >= start,
                            RecurringOccurrence.due_date <= end,
                        ),
                        and_(
                            RecurringOccurrence.status == "paid",
                            or_(
                                and_(
                                    RecurringOccurrence.paid_at >= start_at,
                                    RecurringOccurrence.paid_at < end_at,
                                ),
                                and_(
                                    RecurringOccurrence.paid_at.is_(None),
                                    RecurringOccurrence.due_date >= start,
                                    RecurringOccurrence.due_date <= end,
                                ),
                            ),
                        ),
                    ),
                )
                .order_by(RecurringOccurrence.due_date)
            ).all()
        )

    def personal_planned(
        self,
        user_id: uuid.UUID,
        start: date,
        end: date,
    ) -> list[tuple[PlannedExpense, datetime | None, int | None]]:
        return list(
            self._db.execute(
                select(
                    PlannedExpense,
                    Transaction.paid_at,
                    Transaction.amount_cents,
                )
                .outerjoin(
                    Transaction,
                    PlannedExpense.transaction_id == Transaction.id,
                )
                .where(
                    PlannedExpense.scope == "personal",
                    PlannedExpense.user_id == user_id,
                    or_(
                        and_(
                            PlannedExpense.status.in_(["planned", "committed"]),
                            PlannedExpense.planned_date >= start,
                            PlannedExpense.planned_date <= end,
                        ),
                        and_(
                            PlannedExpense.status == "paid",
                            or_(
                                and_(
                                    Transaction.transaction_date >= start,
                                    Transaction.transaction_date <= end,
                                ),
                                and_(
                                    Transaction.transaction_date.is_(None),
                                    PlannedExpense.planned_date >= start,
                                    PlannedExpense.planned_date <= end,
                                ),
                            ),
                        ),
                    ),
                )
                .order_by(PlannedExpense.planned_date)
            ).all()
        )

    def personal_transactions_for_deduction(
        self,
        user_id: uuid.UUID,
        start: date,
        end: date,
    ) -> list[Transaction]:
        planned_transaction_ids = select(PlannedExpense.transaction_id).where(
            PlannedExpense.user_id == user_id,
            PlannedExpense.transaction_id.is_not(None),
        )
        contribution_transaction_ids = select(HouseholdContribution.transaction_id).where(
            HouseholdContribution.user_id == user_id,
            HouseholdContribution.transaction_id.is_not(None),
        )
        return list(
            self._db.scalars(
                select(Transaction)
                .where(
                    Transaction.user_id == user_id,
                    Transaction.scope == "personal",
                    Transaction.deleted_at.is_(None),
                    Transaction.transaction_date >= start,
                    Transaction.transaction_date <= end,
                    Transaction.recurring_occurrence_id.is_(None),
                    Transaction.id.not_in(planned_transaction_ids),
                    Transaction.id.not_in(contribution_transaction_ids),
                )
                .order_by(
                    Transaction.transaction_date,
                    Transaction.created_at,
                )
            ).all()
        )

    def recent_personal_transactions(
        self,
        user_id: uuid.UUID,
        start: date,
        end: date,
        limit: int = 5,
    ) -> list[Transaction]:
        contribution_transaction_ids = select(HouseholdContribution.transaction_id).where(
            HouseholdContribution.user_id == user_id,
            HouseholdContribution.transaction_id.is_not(None),
        )
        return list(
            self._db.scalars(
                select(Transaction)
                .where(
                    Transaction.user_id == user_id,
                    Transaction.scope == "personal",
                    Transaction.deleted_at.is_(None),
                    Transaction.transaction_date >= start,
                    Transaction.transaction_date <= end,
                    Transaction.id.not_in(contribution_transaction_ids),
                )
                .order_by(
                    Transaction.transaction_date.desc(),
                    Transaction.created_at.desc(),
                )
                .limit(limit)
            ).all()
        )
