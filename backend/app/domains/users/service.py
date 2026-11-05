from collections.abc import Callable
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.core.errors import AppError
from app.core.request_context import request_id_var
from app.domains.audit.repository import AuditRepository
from app.domains.users.models import User


class UserService:
    def __init__(
        self,
        db: Session,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._db = db
        self._now = now or utcnow
        self._audit = AuditRepository(db)

    def update_profile(self, user: User, first_name: str) -> User:
        cleaned_first_name = first_name.strip()
        if not cleaned_first_name:
            raise AppError(
                code="invalid_first_name",
                message="Le prénom ne peut pas être vide.",
                status_code=400,
            )

        user.first_name = cleaned_first_name
        self._audit.add(
            occurred_at=self._now(),
            action="user.profile_updated",
            entity_type="user",
            entity_id=user.id,
            actor_user_id=user.id,
            details={"fields": ["first_name"]},
            request_id=request_id_var.get(),
        )
        self._db.commit()
        return user
