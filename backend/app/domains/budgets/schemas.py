from uuid import UUID

from pydantic import BaseModel, Field


class GroceryBudgetUpdate(BaseModel):
    default_amount_cents: int = Field(ge=0, strict=True)


class GroceryBudgetPublic(BaseModel):
    budget_id: UUID
    name: str
    period: str
    default_amount_cents: int
    allocated_cents: int
    spent_cents: int
    remaining_cents: int
