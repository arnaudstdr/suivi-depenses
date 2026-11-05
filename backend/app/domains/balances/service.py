from collections.abc import Callable
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.core.errors import AppError
from app.core.request_context import request_id_var
from app.domains.audit.repository import AuditRepository
from app.domains.balances.models import PersonalBalanceEntry
from app.domains.balances.repository import PersonalBalanceRepository
from app.domains.users.models import User


class PersonalBalanceService:
    def __init__(
        self,
        db: Session,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._db = db
        self._now = now or utcnow
        self._balances = PersonalBalanceRepository(db)
        self._audit = AuditRepository(db)

    def record(
        self,
        user: User,
        *,
        balance_cents: int,
        recorded_at: datetime | None,
        note: str | None,
    ) -> PersonalBalanceEntry:
        entry = PersonalBalanceEntry(
            user_id=user.id,
            balance_cents=balance_cents,
            recorded_at=recorded_at or self._now(),
            note=note,
        )
        self._balances.add(entry)
        self._db.flush()

        self._audit.add(
            occurred_at=self._now(),
            action="balance.recorded",
            entity_type="personal_balance_entry",
            entity_id=entry.id,
            actor_user_id=user.id,
            request_id=request_id_var.get(),
        )
        self._db.commit()
        return entry

    def latest(self, user: User) -> PersonalBalanceEntry:
        entry = self._balances.get_latest(user.id)
        if entry is None:
            raise AppError(
                code="balance_not_found",
                message="Aucun solde personnel n'a encore été saisi.",
                status_code=404,
            )
        return entry

    def history(
        self,
        user: User,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[PersonalBalanceEntry], int]:
        return self._balances.list_for_user(user.id, limit=limit, offset=offset)
