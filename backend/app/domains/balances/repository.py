import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domains.balances.models import PersonalBalanceEntry


class PersonalBalanceRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_latest(self, user_id: uuid.UUID) -> PersonalBalanceEntry | None:
        return self._db.scalar(
            select(PersonalBalanceEntry)
            .where(PersonalBalanceEntry.user_id == user_id)
            .order_by(
                PersonalBalanceEntry.recorded_at.desc(),
                PersonalBalanceEntry.created_at.desc(),
            )
            .limit(1)
        )

    def list_for_user(
        self,
        user_id: uuid.UUID,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[PersonalBalanceEntry], int]:
        filters = PersonalBalanceEntry.user_id == user_id
        total = int(
            self._db.scalar(select(func.count()).select_from(PersonalBalanceEntry).where(filters))
            or 0
        )
        entries = list(
            self._db.scalars(
                select(PersonalBalanceEntry)
                .where(filters)
                .order_by(
                    PersonalBalanceEntry.recorded_at.desc(),
                    PersonalBalanceEntry.created_at.desc(),
                )
                .limit(limit)
                .offset(offset)
            ).all()
        )
        return entries, total

    def add(self, entry: PersonalBalanceEntry) -> PersonalBalanceEntry:
        self._db.add(entry)
        return entry
