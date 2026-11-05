from datetime import datetime
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.api.pagination import Page


class PersonalBalanceCreate(BaseModel):
    balance_cents: int = Field(strict=True)
    recorded_at: AwareDatetime | None = None
    note: str | None = Field(default=None, max_length=1000)


class PersonalBalancePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    balance_cents: int
    recorded_at: datetime
    note: str | None
    created_at: datetime


PersonalBalancePage = Page[PersonalBalancePublic]
