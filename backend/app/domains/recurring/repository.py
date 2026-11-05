import uuid
from datetime import date
from typing import Any, cast

from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session, joinedload

from app.domains.recurring.models import RecurringExpense, RecurringOccurrence


class RecurringExpenseRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, recurring_id: uuid.UUID) -> RecurringExpense | None:
        return self._db.scalar(
            select(RecurringExpense)
            .options(joinedload(RecurringExpense.category))
            .where(RecurringExpense.id == recurring_id)
        )

    def get_for_update(self, recurring_id: uuid.UUID) -> RecurringExpense | None:
        return self._db.scalar(
            select(RecurringExpense).where(RecurringExpense.id == recurring_id).with_for_update()
        )

    def list_for_member(
        self,
        *,
        user_id: uuid.UUID,
        household_id: uuid.UUID,
        scope: str | None,
        is_active: bool | None,
        category_id: uuid.UUID | None,
        limit: int,
        offset: int,
    ) -> tuple[list[RecurringExpense], int]:
        conditions = [
            or_(
                and_(
                    RecurringExpense.scope == "personal",
                    RecurringExpense.owner_user_id == user_id,
                ),
                and_(
                    RecurringExpense.scope == "shared",
                    RecurringExpense.household_id == household_id,
                ),
            ),
        ]
        if scope is not None:
            conditions.append(RecurringExpense.scope == scope)
        if is_active is not None:
            conditions.append(RecurringExpense.is_active.is_(is_active))
        if category_id is not None:
            conditions.append(RecurringExpense.category_id == category_id)

        total = int(
            self._db.scalar(select(func.count()).select_from(RecurringExpense).where(*conditions))
            or 0
        )
        items = list(
            self._db.scalars(
                select(RecurringExpense)
                .options(joinedload(RecurringExpense.category))
                .where(*conditions)
                .order_by(RecurringExpense.created_at.desc())
                .limit(limit)
                .offset(offset)
            ).all()
        )
        return items, total

    def list_active_for_member(
        self,
        user_id: uuid.UUID,
        household_id: uuid.UUID,
    ) -> list[RecurringExpense]:
        return list(
            self._db.scalars(
                select(RecurringExpense)
                .where(
                    RecurringExpense.is_active.is_(True),
                    or_(
                        and_(
                            RecurringExpense.scope == "personal",
                            RecurringExpense.owner_user_id == user_id,
                        ),
                        and_(
                            RecurringExpense.scope == "shared",
                            RecurringExpense.household_id == household_id,
                        ),
                    ),
                )
                .order_by(RecurringExpense.created_at)
            ).all()
        )

    def list_active_shared(self, household_id: uuid.UUID) -> list[RecurringExpense]:
        return list(
            self._db.scalars(
                select(RecurringExpense)
                .where(
                    RecurringExpense.is_active.is_(True),
                    RecurringExpense.scope == "shared",
                    RecurringExpense.household_id == household_id,
                )
                .order_by(RecurringExpense.created_at)
            ).all()
        )

    def list_all_active(self) -> list[RecurringExpense]:
        return list(
            self._db.scalars(
                select(RecurringExpense)
                .where(RecurringExpense.is_active.is_(True))
                .order_by(RecurringExpense.created_at)
            ).all()
        )

    def add(self, recurring: RecurringExpense) -> RecurringExpense:
        self._db.add(recurring)
        return recurring


class RecurringOccurrenceRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, occurrence_id: uuid.UUID) -> RecurringOccurrence | None:
        return self._db.get(RecurringOccurrence, occurrence_id)

    def get_for_update(self, occurrence_id: uuid.UUID) -> RecurringOccurrence | None:
        return self._db.scalar(
            select(RecurringOccurrence)
            .where(RecurringOccurrence.id == occurrence_id)
            .with_for_update()
        )

    def existing_due_dates(
        self,
        recurring_id: uuid.UUID,
        start: date,
        end: date,
    ) -> set[date]:
        return set(
            self._db.scalars(
                select(RecurringOccurrence.due_date).where(
                    RecurringOccurrence.recurring_expense_id == recurring_id,
                    RecurringOccurrence.due_date >= start,
                    RecurringOccurrence.due_date <= end,
                )
            ).all()
        )

    def list_for_recurring(
        self,
        recurring_id: uuid.UUID,
        *,
        start: date,
        end: date,
        status: str | None,
    ) -> list[RecurringOccurrence]:
        conditions = [
            RecurringOccurrence.recurring_expense_id == recurring_id,
            RecurringOccurrence.due_date >= start,
            RecurringOccurrence.due_date <= end,
        ]
        if status is not None:
            conditions.append(RecurringOccurrence.status == status)
        return list(
            self._db.scalars(
                select(RecurringOccurrence)
                .where(*conditions)
                .order_by(RecurringOccurrence.due_date)
            ).all()
        )

    def insert_missing(self, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        statement = (
            insert(RecurringOccurrence)
            .values(rows)
            .on_conflict_do_nothing(
                index_elements=[
                    RecurringOccurrence.recurring_expense_id,
                    RecurringOccurrence.due_date,
                ]
            )
            .returning(RecurringOccurrence.id)
        )
        result = cast(CursorResult[Any], self._db.execute(statement))
        return len(result.scalars().all())

    def add(self, occurrence: RecurringOccurrence) -> RecurringOccurrence:
        self._db.add(occurrence)
        return occurrence
