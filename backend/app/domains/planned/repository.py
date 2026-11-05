import uuid
from datetime import date

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.domains.planned.models import PlannedExpense


class PlannedExpenseRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, planned_id: uuid.UUID) -> PlannedExpense | None:
        return self._db.scalar(
            select(PlannedExpense)
            .options(joinedload(PlannedExpense.category))
            .where(PlannedExpense.id == planned_id)
        )

    def get_for_update(self, planned_id: uuid.UUID) -> PlannedExpense | None:
        return self._db.scalar(
            select(PlannedExpense).where(PlannedExpense.id == planned_id).with_for_update()
        )

    def list_for_member(
        self,
        *,
        user_id: uuid.UUID,
        household_id: uuid.UUID,
        scope: str | None,
        status: str | None,
        category_id: uuid.UUID | None,
        date_from: date | None,
        date_to: date | None,
        limit: int,
        offset: int,
    ) -> tuple[list[PlannedExpense], int]:
        conditions = [
            or_(
                and_(
                    PlannedExpense.scope == "personal",
                    PlannedExpense.user_id == user_id,
                ),
                and_(
                    PlannedExpense.scope == "shared",
                    PlannedExpense.household_id == household_id,
                ),
            ),
        ]
        if scope is not None:
            conditions.append(PlannedExpense.scope == scope)
        if status is not None:
            conditions.append(PlannedExpense.status == status)
        if category_id is not None:
            conditions.append(PlannedExpense.category_id == category_id)
        if date_from is not None:
            conditions.append(PlannedExpense.planned_date >= date_from)
        if date_to is not None:
            conditions.append(PlannedExpense.planned_date <= date_to)

        total = int(
            self._db.scalar(select(func.count()).select_from(PlannedExpense).where(*conditions))
            or 0
        )
        items = list(
            self._db.scalars(
                select(PlannedExpense)
                .options(joinedload(PlannedExpense.category))
                .where(*conditions)
                .order_by(
                    PlannedExpense.planned_date.desc(),
                    PlannedExpense.created_at.desc(),
                )
                .limit(limit)
                .offset(offset)
            ).all()
        )
        return items, total

    def add(self, planned: PlannedExpense) -> PlannedExpense:
        self._db.add(planned)
        return planned
