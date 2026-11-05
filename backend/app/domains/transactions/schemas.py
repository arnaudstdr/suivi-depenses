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

TransactionLabel = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]


class TransactionCreate(BaseModel):
    label: TransactionLabel
    amount_cents: int = Field(gt=0, strict=True)
    transaction_date: date
    category_id: UUID
    scope: Literal["personal", "shared"]
    transaction_type: Literal["expense", "refund"] = "expense"
    original_transaction_id: UUID | None = None
    budget_id: UUID | None = None
    paid_at: AwareDatetime | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_refund_link(self) -> "TransactionCreate":
        if self.transaction_type == "refund" and self.original_transaction_id is None:
            raise ValueError("Un remboursement doit référencer la dépense d'origine.")
        if self.transaction_type == "expense" and self.original_transaction_id is not None:
            raise ValueError("Une dépense ne peut pas référencer une transaction d'origine.")
        return self


class TransactionUpdate(BaseModel):
    label: TransactionLabel | None = None
    amount_cents: int | None = Field(default=None, gt=0, strict=True)
    transaction_date: date | None = None
    category_id: UUID | None = None
    paid_at: AwareDatetime | None = None
    notes: str | None = Field(default=None, max_length=2000)


class TransactionPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    household_id: UUID | None
    user_id: UUID
    category_id: UUID
    label: str
    amount_cents: int
    transaction_type: str
    scope: str
    budget_id: UUID | None
    transaction_date: date
    paid_at: datetime | None
    status: str
    original_transaction_id: UUID | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


TransactionPage = Page[TransactionPublic]
