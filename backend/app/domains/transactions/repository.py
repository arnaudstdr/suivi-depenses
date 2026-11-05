import uuid
from datetime import date

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.domains.allocations.models import HouseholdContribution
from app.domains.planned.models import PlannedExpense
from app.domains.recurring.models import RecurringOccurrence
from app.domains.transactions.models import Transaction


class TransactionRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, transaction_id: uuid.UUID) -> Transaction | None:
        return self._db.scalar(
            select(Transaction)
            .options(joinedload(Transaction.category))
            .where(Transaction.id == transaction_id)
        )

    def list_for_member(
        self,
        *,
        user_id: uuid.UUID,
        household_id: uuid.UUID,
        scope: str | None,
        category_id: uuid.UUID | None,
        date_from: date | None,
        date_to: date | None,
        status: str | None,
        search: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Transaction], int]:
        conditions = [
            Transaction.deleted_at.is_(None),
            or_(
                and_(
                    Transaction.scope == "personal",
                    Transaction.user_id == user_id,
                ),
                and_(
                    Transaction.scope == "shared",
                    Transaction.household_id == household_id,
                ),
            ),
        ]
        if scope is not None:
            conditions.append(Transaction.scope == scope)
        if category_id is not None:
            conditions.append(Transaction.category_id == category_id)
        if date_from is not None:
            conditions.append(Transaction.transaction_date >= date_from)
        if date_to is not None:
            conditions.append(Transaction.transaction_date <= date_to)
        if status is not None:
            conditions.append(Transaction.status == status)
        if search:
            conditions.append(Transaction.label.icontains(search, autoescape=True))

        total = int(
            self._db.scalar(select(func.count()).select_from(Transaction).where(*conditions)) or 0
        )
        items = list(
            self._db.scalars(
                select(Transaction)
                .options(joinedload(Transaction.category))
                .where(*conditions)
                .order_by(
                    Transaction.transaction_date.desc(),
                    Transaction.created_at.desc(),
                )
                .limit(limit)
                .offset(offset)
            ).all()
        )
        return items, total

    def list_for_budget(
        self,
        *,
        budget_id: uuid.UUID,
        date_from: date,
        date_to: date,
        limit: int,
        offset: int,
    ) -> tuple[list[Transaction], int]:
        conditions = [
            Transaction.budget_id == budget_id,
            Transaction.deleted_at.is_(None),
            Transaction.transaction_date >= date_from,
            Transaction.transaction_date <= date_to,
        ]
        total = int(
            self._db.scalar(select(func.count()).select_from(Transaction).where(*conditions)) or 0
        )
        items = list(
            self._db.scalars(
                select(Transaction)
                .options(joinedload(Transaction.category))
                .where(*conditions)
                .order_by(
                    Transaction.transaction_date.desc(),
                    Transaction.created_at.desc(),
                )
                .limit(limit)
                .offset(offset)
            ).all()
        )
        return items, total

    def duplicate_keys(
        self,
        *,
        user_id: uuid.UUID,
        household_id: uuid.UUID,
        scope: str,
        date_from: date,
        date_to: date,
    ) -> set[tuple[date, int, str, uuid.UUID]]:
        conditions = [
            Transaction.deleted_at.is_(None),
            Transaction.scope == scope,
            Transaction.transaction_type == "expense",
            Transaction.transaction_date >= date_from,
            Transaction.transaction_date <= date_to,
        ]
        if scope == "personal":
            conditions.append(Transaction.user_id == user_id)
        else:
            conditions.append(Transaction.household_id == household_id)
        rows = self._db.execute(
            select(
                Transaction.transaction_date,
                Transaction.amount_cents,
                Transaction.label,
                Transaction.category_id,
            ).where(*conditions)
        ).all()
        return {
            (row.transaction_date, row.amount_cents, row.label.strip().casefold(), row.category_id)
            for row in rows
        }

    def sum_refunds(self, original_transaction_id: uuid.UUID) -> int:
        total = self._db.scalar(
            select(func.coalesce(func.sum(Transaction.amount_cents), 0)).where(
                Transaction.original_transaction_id == original_transaction_id,
                Transaction.transaction_type == "refund",
                Transaction.deleted_at.is_(None),
            )
        )
        return int(total or 0)

    def linked_source(self, transaction_id: uuid.UUID) -> str | None:
        if self._db.scalar(
            select(RecurringOccurrence.id)
            .where(RecurringOccurrence.transaction_id == transaction_id)
            .limit(1)
        ):
            return "recurring_occurrence"
        if self._db.scalar(
            select(PlannedExpense.id)
            .where(PlannedExpense.transaction_id == transaction_id)
            .limit(1)
        ):
            return "planned_expense"
        if self._db.scalar(
            select(HouseholdContribution.id)
            .where(HouseholdContribution.transaction_id == transaction_id)
            .limit(1)
        ):
            return "household_contribution"
        return None

    def add(self, transaction: Transaction) -> Transaction:
        self._db.add(transaction)
        return transaction
