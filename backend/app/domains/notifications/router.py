from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_session, require_csrf
from app.api.pagination import Page, PageParams
from app.domains.notifications.schemas import (
    NotificationPreferencePublic,
    NotificationPreferenceUpdateRequest,
    NotificationPublic,
    NotificationUnreadCount,
)
from app.domains.notifications.service import NotificationService
from app.domains.users.models import User

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=Page[NotificationPublic])
def list_notifications(
    unread_only: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
    params: PageParams = Depends(),
) -> Page[NotificationPublic]:
    items, total = NotificationService(db).list_notifications(
        user,
        unread_only=unread_only,
        limit=params.limit,
        offset=params.offset,
    )
    return Page[NotificationPublic](
        items=items,
        total=total,
        limit=params.limit,
        offset=params.offset,
    )


@router.get("/unread-count", response_model=NotificationUnreadCount)
def unread_count(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> NotificationUnreadCount:
    return NotificationUnreadCount(count=NotificationService(db).unread_count(user))


@router.post("/read-all")
def mark_all_read(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
    _: None = Depends(require_csrf),
) -> dict[str, int]:
    return {"updated": NotificationService(db).mark_all_read(user)}


@router.get("/preferences", response_model=list[NotificationPreferencePublic])
def get_preferences(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> list[NotificationPreferencePublic]:
    return NotificationService(db).get_preferences(user)


@router.put("/preferences", response_model=list[NotificationPreferencePublic])
def update_preferences(
    payload: NotificationPreferenceUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
    _: None = Depends(require_csrf),
) -> list[NotificationPreferencePublic]:
    return NotificationService(db).update_preferences(user, payload.preferences)


@router.post("/{notification_id}/read", response_model=NotificationPublic)
def mark_read(
    notification_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
    _: None = Depends(require_csrf),
) -> NotificationPublic:
    return NotificationService(db).mark_read(user, notification_id)
