import uuid
from collections.abc import Callable
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.core.errors import AppError
from app.core.request_context import request_id_var
from app.domains.audit.repository import AuditRepository
from app.domains.notifications.constants import (
    DEFAULT_IN_APP_ENABLED,
    DEFAULT_PUSH_ENABLED,
    NOTIFICATION_TYPES,
)
from app.domains.notifications.models import NotificationPreference
from app.domains.notifications.repository import NotificationRepository
from app.domains.notifications.schemas import (
    NotificationPreferencePublic,
    NotificationPreferenceUpdate,
    NotificationPublic,
)
from app.domains.users.models import User


class NotificationService:
    def __init__(
        self,
        db: Session,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._db = db
        self._now = now or utcnow
        self._notifications = NotificationRepository(db)
        self._audit = AuditRepository(db)

    def notify(
        self,
        *,
        user_id: uuid.UUID,
        notification_type: str,
        title: str,
        household_id: uuid.UUID | None = None,
        body: str | None = None,
        entity_type: str | None = None,
        entity_id: uuid.UUID | None = None,
        dedupe_key: str | None = None,
        commit: bool = True,
    ) -> uuid.UUID | None:
        if not self._is_in_app_enabled(user_id, notification_type):
            return None
        created = self._notifications.insert_idempotent(
            notification_id=uuid.uuid4(),
            user_id=user_id,
            household_id=household_id,
            notification_type=notification_type,
            title=title,
            body=body,
            entity_type=entity_type,
            entity_id=entity_id,
            dedupe_key=dedupe_key,
        )
        if commit:
            self._db.commit()
        return created

    def list_notifications(
        self,
        user: User,
        *,
        unread_only: bool,
        limit: int,
        offset: int,
    ) -> tuple[list[NotificationPublic], int]:
        items, total = self._notifications.list_for_user(
            user.id,
            unread_only=unread_only,
            limit=limit,
            offset=offset,
        )
        return [
            NotificationPublic(
                id=item.id,
                type=item.type,
                title=item.title,
                body=item.body,
                entity_type=item.entity_type,
                entity_id=item.entity_id,
                read_at=item.read_at,
                created_at=item.created_at,
            )
            for item in items
        ], total

    def unread_count(self, user: User) -> int:
        return self._notifications.unread_count(user.id)

    def mark_read(self, user: User, notification_id: uuid.UUID) -> NotificationPublic:
        notification = self._notifications.get_for_update(notification_id, user.id)
        if notification is None:
            raise AppError(
                code="not_found",
                message="Notification introuvable.",
                status_code=404,
            )
        if notification.read_at is None:
            notification.read_at = self._now()
            self._db.commit()
        return NotificationPublic(
            id=notification.id,
            type=notification.type,
            title=notification.title,
            body=notification.body,
            entity_type=notification.entity_type,
            entity_id=notification.entity_id,
            read_at=notification.read_at,
            created_at=notification.created_at,
        )

    def mark_all_read(self, user: User) -> int:
        count = self._notifications.mark_all_read(user.id, self._now())
        self._db.commit()
        return count

    def get_preferences(self, user: User) -> list[NotificationPreferencePublic]:
        stored = {
            preference.type: preference
            for preference in self._notifications.list_preferences(user.id)
        }
        return [
            NotificationPreferencePublic(
                type=notification_type,
                in_app_enabled=(
                    stored[notification_type].in_app_enabled
                    if notification_type in stored
                    else DEFAULT_IN_APP_ENABLED
                ),
                push_enabled=(
                    stored[notification_type].push_enabled
                    if notification_type in stored
                    else DEFAULT_PUSH_ENABLED
                ),
            )
            for notification_type in NOTIFICATION_TYPES
        ]

    def update_preferences(
        self,
        user: User,
        updates: list[NotificationPreferenceUpdate],
    ) -> list[NotificationPreferencePublic]:
        seen: set[str] = set()
        for update in updates:
            if update.type not in NOTIFICATION_TYPES:
                raise AppError(
                    code="invalid_notification_type",
                    message=f"Type de notification inconnu : {update.type}.",
                    status_code=422,
                )
            if update.type in seen:
                raise AppError(
                    code="duplicate_notification_type",
                    message="Un type de notification est présent plusieurs fois.",
                    status_code=422,
                )
            seen.add(update.type)

            preference = self._notifications.get_preference(user.id, update.type)
            if preference is None:
                preference = NotificationPreference(
                    user_id=user.id,
                    type=update.type,
                    in_app_enabled=update.in_app_enabled,
                    push_enabled=update.push_enabled,
                )
                self._notifications.add_preference(preference)
            else:
                preference.in_app_enabled = update.in_app_enabled
                preference.push_enabled = update.push_enabled

        self._audit.add(
            occurred_at=self._now(),
            action="notification.preferences_updated",
            entity_type="notification_preference",
            actor_user_id=user.id,
            details={"types": sorted(seen)},
            request_id=request_id_var.get(),
        )
        self._db.commit()
        return self.get_preferences(user)

    def _is_in_app_enabled(
        self,
        user_id: uuid.UUID,
        notification_type: str,
    ) -> bool:
        preference = self._notifications.get_preference(user_id, notification_type)
        if preference is None:
            return DEFAULT_IN_APP_ENABLED
        return preference.in_app_enabled
