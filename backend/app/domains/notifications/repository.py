import uuid
from datetime import datetime
from typing import Any, cast

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from app.domains.notifications.models import Notification, NotificationPreference


class NotificationRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def add(self, notification: Notification) -> Notification:
        self._db.add(notification)
        return notification

    def insert_idempotent(
        self,
        *,
        notification_id: uuid.UUID,
        user_id: uuid.UUID,
        household_id: uuid.UUID | None,
        notification_type: str,
        title: str,
        body: str | None,
        entity_type: str | None,
        entity_id: uuid.UUID | None,
        dedupe_key: str | None,
    ) -> uuid.UUID | None:
        values: dict[str, Any] = {
            "id": notification_id,
            "user_id": user_id,
            "household_id": household_id,
            "type": notification_type,
            "title": title,
            "body": body,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "dedupe_key": dedupe_key,
        }
        insert_statement: Any = insert(Notification).values(**values)
        if dedupe_key is not None:
            insert_statement = insert_statement.on_conflict_do_nothing(
                index_elements=["user_id", "dedupe_key"],
            )
        statement = insert_statement.returning(Notification.id)
        result = cast(CursorResult[Any], self._db.execute(statement))
        return result.scalar_one_or_none()

    def list_for_user(
        self,
        user_id: uuid.UUID,
        *,
        unread_only: bool,
        limit: int,
        offset: int,
    ) -> tuple[list[Notification], int]:
        conditions = [Notification.user_id == user_id]
        if unread_only:
            conditions.append(Notification.read_at.is_(None))
        total = int(
            self._db.scalar(select(func.count()).select_from(Notification).where(*conditions)) or 0
        )
        items = list(
            self._db.scalars(
                select(Notification)
                .where(*conditions)
                .order_by(Notification.created_at.desc(), Notification.id)
                .limit(limit)
                .offset(offset)
            ).all()
        )
        return items, total

    def unread_count(self, user_id: uuid.UUID) -> int:
        return int(
            self._db.scalar(
                select(func.count())
                .select_from(Notification)
                .where(
                    Notification.user_id == user_id,
                    Notification.read_at.is_(None),
                )
            )
            or 0
        )

    def get_for_update(
        self,
        notification_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Notification | None:
        return self._db.scalar(
            select(Notification)
            .where(
                Notification.id == notification_id,
                Notification.user_id == user_id,
            )
            .with_for_update()
        )

    def mark_all_read(self, user_id: uuid.UUID, read_at: datetime) -> int:
        result = cast(
            CursorResult[Any],
            self._db.execute(
                update(Notification)
                .where(
                    Notification.user_id == user_id,
                    Notification.read_at.is_(None),
                )
                .values(read_at=read_at)
            ),
        )
        return int(result.rowcount or 0)

    def get_preference(
        self,
        user_id: uuid.UUID,
        notification_type: str,
    ) -> NotificationPreference | None:
        return self._db.scalar(
            select(NotificationPreference).where(
                NotificationPreference.user_id == user_id,
                NotificationPreference.type == notification_type,
            )
        )

    def list_preferences(self, user_id: uuid.UUID) -> list[NotificationPreference]:
        return list(
            self._db.scalars(
                select(NotificationPreference)
                .where(NotificationPreference.user_id == user_id)
                .order_by(NotificationPreference.type)
            ).all()
        )

    def add_preference(
        self,
        preference: NotificationPreference,
    ) -> NotificationPreference:
        self._db.add(preference)
        return preference
