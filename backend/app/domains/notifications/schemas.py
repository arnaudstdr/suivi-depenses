from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class NotificationPublic(BaseModel):
    id: UUID
    type: str
    title: str
    body: str | None
    entity_type: str | None
    entity_id: UUID | None
    read_at: datetime | None
    created_at: datetime


class NotificationUnreadCount(BaseModel):
    count: int


class NotificationPreferencePublic(BaseModel):
    type: str
    in_app_enabled: bool
    push_enabled: bool


class NotificationPreferenceUpdate(BaseModel):
    type: str
    in_app_enabled: bool
    push_enabled: bool = False


class NotificationPreferenceUpdateRequest(BaseModel):
    preferences: list[NotificationPreferenceUpdate] = Field(min_length=1)
