from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel


class DashboardBalance(BaseModel):
    balance_cents: int
    recorded_at: datetime


class DashboardDeductions(BaseModel):
    personal_recurring_remaining_cents: int
    personal_planned_remaining_cents: int
    personal_transactions_remaining_cents: int
    household_contribution_remaining_cents: int
    household_contribution_status: str
    total_cents: int


class DashboardGroceryBudget(BaseModel):
    allocated_cents: int
    spent_cents: int
    remaining_cents: int


class DashboardUpcomingRecurring(BaseModel):
    occurrence_id: UUID
    recurring_expense_id: UUID
    label: str
    due_date: date
    amount_cents: int
    status: str


class DashboardRecentTransaction(BaseModel):
    id: UUID
    label: str
    amount_cents: int
    transaction_date: date
    category_id: UUID
    transaction_type: str


class DashboardResponse(BaseModel):
    period: str
    currency: str
    personal_balance: DashboardBalance
    deductions: DashboardDeductions
    available_forecast_cents: int
    grocery_budget: DashboardGroceryBudget
    upcoming_recurring: list[DashboardUpcomingRecurring]
    recent_personal_transactions: list[DashboardRecentTransaction]
