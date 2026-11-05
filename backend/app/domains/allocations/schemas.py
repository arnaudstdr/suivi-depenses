from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, EmailStr, Field


class AllocationMemberInput(BaseModel):
    user_id: UUID
    percentage: Decimal = Field(
        ge=0,
        le=100,
        max_digits=6,
        decimal_places=3,
    )


class AllocationRuleUpdate(BaseModel):
    members: list[AllocationMemberInput] = Field(min_length=1)


class AllocationMemberPublic(BaseModel):
    user_id: UUID
    email: EmailStr
    first_name: str
    percentage: Decimal


class AllocationRulePublic(BaseModel):
    id: UUID
    name: str
    is_default: bool
    members: list[AllocationMemberPublic]


class ContributionMarkTransferred(BaseModel):
    transferred_at: AwareDatetime
    transferred_amount_cents: int = Field(gt=0, strict=True)
    note: str | None = Field(default=None, max_length=2000)


class ContributionCorrectTransfer(BaseModel):
    transferred_at: AwareDatetime
    transferred_amount_cents: int = Field(gt=0, strict=True)
    note: str | None = Field(default=None, max_length=2000)


class ContributionPublic(BaseModel):
    id: UUID
    household_id: UUID
    user_id: UUID
    email: EmailStr
    first_name: str
    period: str
    period_start: date
    amount_cents: int
    allocation_percentage: Decimal
    status: str
    transferred_at: datetime | None
    transferred_amount_cents: int | None
    transaction_id: UUID | None
    created_at: datetime
    updated_at: datetime
