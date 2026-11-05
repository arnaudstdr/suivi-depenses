import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.domains.audit.models import AuditLog


class AuditRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def add(
        self,
        *,
        occurred_at: datetime,
        action: str,
        entity_type: str,
        entity_id: uuid.UUID | None = None,
        actor_user_id: uuid.UUID | None = None,
        household_id: uuid.UUID | None = None,
        details: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> AuditLog:
        log = AuditLog(
            occurred_at=occurred_at,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_user_id=actor_user_id,
            household_id=household_id,
            details=details,
            request_id=request_id,
        )
        self._db.add(log)
        return log
