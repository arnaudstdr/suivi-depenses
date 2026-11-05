import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domains.budgets.models import Budget, BudgetPeriod


class BudgetRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_grocery(self, household_id: uuid.UUID) -> Budget | None:
        return self._db.scalar(
            select(Budget).where(
                Budget.household_id == household_id,
                Budget.budget_type == "grocery",
            )
        )

    def get_period(self, budget_id: uuid.UUID, period_start: date) -> BudgetPeriod | None:
        return self._db.scalar(
            select(BudgetPeriod).where(
                BudgetPeriod.budget_id == budget_id,
                BudgetPeriod.period_start == period_start,
            )
        )

    def add_period(self, period: BudgetPeriod) -> BudgetPeriod:
        self._db.add(period)
        return period
