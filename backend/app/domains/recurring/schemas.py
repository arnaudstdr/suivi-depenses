from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from app.api.pagination import Page

RecurringLabel = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]
Frequency = Literal["weekly", "monthly", "quarterly", "semiannual", "yearly"]


class RecurringExpenseCreate(BaseModel):
    label: RecurringLabel
    amount_cents: int | None = Field(default=None, gt=0, strict=True)
    category_id: UUID
    scope: Literal["personal", "shared"]
    frequency: Frequency
    start_date: date
    end_date: date | None = None
    due_day: int | None = Field(default=None, ge=1, le=31)
    amount_is_variable: bool = False

    @model_validator(mode="after")
    def validate_amount_and_dates(self) -> "RecurringExpenseCreate":
        if not self.amount_is_variable and self.amount_cents is None:
            raise ValueError("Un montant est obligatoire pour une charge fixe.")
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("La date de fin doit être postérieure à la date de début.")
        return self


class RecurringExpenseUpdate(BaseModel):
    label: RecurringLabel | None = None
    amount_cents: int | None = Field(default=None, gt=0, strict=True)
    category_id: UUID | None = None
    frequency: Frequency | None = None
    start_date: date | None = None
    end_date: date | None = None
    due_day: int | None = Field(default=None, ge=1, le=31)
    amount_is_variable: bool | None = None


class RecurringExpensePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    household_id: UUID | None
    owner_user_id: UUID
    category_id: UUID
    allocation_rule_id: UUID | None
    label: str
    amount_cents: int | None
    scope: str
    frequency: str
    start_date: date
    end_date: date | None
    due_day: int | None
    amount_is_variable: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class RecurringOccurrencePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    recurring_expense_id: UUID
    due_date: date
    expected_amount_cents: int | None
    confirmed_amount_cents: int | None
    confirmed_at: datetime | None
    status: str
    paid_at: datetime | None
    payment_amount_cents: int | None
    payment_note: str | None
    skipped_at: datetime | None
    skip_reason: str | None
    transaction_id: UUID | None
    created_at: datetime
    updated_at: datetime


class RecurringOccurrenceMarkPaid(BaseModel):
    paid_at: AwareDatetime
    payment_amount_cents: int | None = Field(default=None, gt=0, strict=True)
    note: str | None = Field(default=None, max_length=2000)


class RecurringOccurrenceConfirmAmount(BaseModel):
    confirmed_amount_cents: int = Field(gt=0, strict=True)


class RecurringOccurrenceSkip(BaseModel):
    reason: str | None = Field(default=None, max_length=2000)


class RecurringOccurrenceCorrectPayment(BaseModel):
    paid_at: AwareDatetime
    payment_amount_cents: int = Field(gt=0, strict=True)
    note: str | None = Field(default=None, max_length=2000)


RecurringExpensePage = Page[RecurringExpensePublic]
