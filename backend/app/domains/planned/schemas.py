from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
)

from app.api.pagination import Page

PlannedLabel = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]


class PlannedExpenseCreate(BaseModel):
    label: PlannedLabel
    amount_cents: int = Field(gt=0, strict=True)
    planned_date: date
    category_id: UUID
    scope: Literal["personal", "shared"]
    status: Literal["planned", "committed"] = "planned"


class PlannedExpenseUpdate(BaseModel):
    label: PlannedLabel | None = None
    amount_cents: int | None = Field(default=None, gt=0, strict=True)
    planned_date: date | None = None
    category_id: UUID | None = None
    status: Literal["planned", "committed"] | None = None


class PlannedExpenseMarkPaid(BaseModel):
    paid_at: AwareDatetime
    payment_amount_cents: int | None = Field(default=None, gt=0, strict=True)
    note: str | None = Field(default=None, max_length=2000)


class PlannedExpenseCorrectPayment(BaseModel):
    paid_at: AwareDatetime
    payment_amount_cents: int = Field(gt=0, strict=True)
    note: str | None = Field(default=None, max_length=2000)


class PlannedExpensePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    household_id: UUID | None
    user_id: UUID
    category_id: UUID
    label: str
    amount_cents: int
    scope: str
    planned_date: date
    status: str
    transaction_id: UUID | None
    created_at: datetime
    updated_at: datetime


PlannedExpensePage = Page[PlannedExpensePublic]
