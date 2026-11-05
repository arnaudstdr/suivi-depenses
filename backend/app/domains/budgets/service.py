import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Final

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.core.errors import AppError
from app.core.periods import current_period, parse_period
from app.core.request_context import request_id_var
from app.domains.audit.repository import AuditRepository
from app.domains.budgets.models import Budget, BudgetPeriod
from app.domains.budgets.repository import BudgetRepository
from app.domains.categories.constants import GROCERY_CATEGORY_ID
from app.domains.categories.seed import ensure_default_categories
from app.domains.households.models import HouseholdMember
from app.domains.transactions.models import Transaction

GROCERY_BUDGET_NAME: Final = "Budget courses"
GROCERY_BUDGET_DEFAULT_CENTS: Final = 49_000


def ensure_grocery_budget(db: Session, household_id: uuid.UUID) -> Budget:
    budget = BudgetRepository(db).get_grocery(household_id)
    if budget is not None:
        return budget

    ensure_default_categories(db)
    budget = Budget(
        household_id=household_id,
        name=GROCERY_BUDGET_NAME,
        budget_type="grocery",
        category_id=GROCERY_CATEGORY_ID,
        default_amount_cents=GROCERY_BUDGET_DEFAULT_CENTS,
        is_active=True,
    )
    db.add(budget)
    db.flush()
    return budget


@dataclass(frozen=True)
class GrocerySummary:
    budget: Budget
    period: BudgetPeriod
    allocated_cents: int
    spent_cents: int
    remaining_cents: int


class BudgetService:
    def __init__(
        self,
        db: Session,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._db = db
        self._now = now or utcnow
        self._budgets = BudgetRepository(db)
        self._audit = AuditRepository(db)

    def get_grocery_summary(
        self,
        membership: HouseholdMember,
        period: str | None,
    ) -> GrocerySummary:
        budget = ensure_grocery_budget(self._db, membership.household_id)
        period_value = period or current_period(membership.household.timezone)
        start, end = parse_period(period_value)

        budget_period = self._budgets.get_period(budget.id, start)
        created = False
        if budget_period is None:
            budget_period = BudgetPeriod(
                budget_id=budget.id,
                period_start=start,
                period_end=end,
                allocated_amount_cents=budget.default_amount_cents,
                status="open",
            )
            self._budgets.add_period(budget_period)
            created = True

        if created:
            self._db.commit()

        spent = self._spent_cents(budget.id, start, end)
        return GrocerySummary(
            budget=budget,
            period=budget_period,
            allocated_cents=budget_period.allocated_amount_cents,
            spent_cents=spent,
            remaining_cents=budget_period.allocated_amount_cents - spent,
        )

    def update_grocery_budget(
        self,
        membership: HouseholdMember,
        default_amount_cents: int,
    ) -> GrocerySummary:
        if membership.role != "owner":
            raise AppError(
                code="forbidden",
                message="Seul le propriétaire du foyer peut modifier le budget.",
                status_code=403,
            )

        budget = ensure_grocery_budget(self._db, membership.household_id)
        budget.default_amount_cents = default_amount_cents

        period_value = current_period(membership.household.timezone)
        start, end = parse_period(period_value)
        budget_period = self._budgets.get_period(budget.id, start)
        if budget_period is None:
            budget_period = BudgetPeriod(
                budget_id=budget.id,
                period_start=start,
                period_end=end,
                allocated_amount_cents=default_amount_cents,
                status="open",
            )
            self._budgets.add_period(budget_period)
        elif budget_period.status == "open":
            budget_period.allocated_amount_cents = default_amount_cents

        self._audit.add(
            occurred_at=self._now(),
            action="budget.grocery_updated",
            entity_type="budget",
            entity_id=budget.id,
            actor_user_id=membership.user_id,
            household_id=membership.household_id,
            request_id=request_id_var.get(),
        )
        self._db.commit()

        spent = self._spent_cents(budget.id, start, end)
        return GrocerySummary(
            budget=budget,
            period=budget_period,
            allocated_cents=budget_period.allocated_amount_cents,
            spent_cents=spent,
            remaining_cents=budget_period.allocated_amount_cents - spent,
        )

    def _spent_cents(self, budget_id: uuid.UUID, start: date, end: date) -> int:
        signed_amount = case(
            (Transaction.transaction_type == "expense", Transaction.amount_cents),
            else_=-Transaction.amount_cents,
        )
        total = self._db.scalar(
            select(func.coalesce(func.sum(signed_amount), 0)).where(
                Transaction.budget_id == budget_id,
                Transaction.deleted_at.is_(None),
                Transaction.scope == "shared",
                Transaction.transaction_date >= start,
                Transaction.transaction_date <= end,
            )
        )
        return max(int(total or 0), 0)
