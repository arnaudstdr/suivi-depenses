from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_current_membership,
    get_session,
    require_csrf,
    require_owner,
)
from app.api.pagination import Page, PageParams
from app.domains.budgets.schemas import GroceryBudgetPublic, GroceryBudgetUpdate
from app.domains.budgets.service import BudgetService, GrocerySummary
from app.domains.households.models import HouseholdMember
from app.domains.transactions.schemas import TransactionPublic
from app.domains.transactions.service import TransactionService

router = APIRouter(prefix="/households/me/grocery-budget", tags=["budgets"])


def _summary_response(summary: GrocerySummary, period: str) -> GroceryBudgetPublic:
    return GroceryBudgetPublic(
        budget_id=summary.budget.id,
        name=summary.budget.name,
        period=period,
        default_amount_cents=summary.budget.default_amount_cents,
        allocated_cents=summary.allocated_cents,
        spent_cents=summary.spent_cents,
        remaining_cents=summary.remaining_cents,
    )


@router.get("", response_model=GroceryBudgetPublic)
def get_grocery_budget(
    period: str | None = None,
    membership: HouseholdMember = Depends(get_current_membership),
    db: Session = Depends(get_session),
) -> GroceryBudgetPublic:
    summary = BudgetService(db).get_grocery_summary(membership, period)
    resolved_period = period or summary.period.period_start.strftime("%Y-%m")
    return _summary_response(summary, resolved_period)


@router.patch("", response_model=GroceryBudgetPublic)
def update_grocery_budget(
    payload: GroceryBudgetUpdate,
    membership: HouseholdMember = Depends(require_owner),
    db: Session = Depends(get_session),
    _: None = Depends(require_csrf),
) -> GroceryBudgetPublic:
    summary = BudgetService(db).update_grocery_budget(
        membership,
        payload.default_amount_cents,
    )
    resolved_period = summary.period.period_start.strftime("%Y-%m")
    return _summary_response(summary, resolved_period)


@router.get("/transactions", response_model=Page[TransactionPublic])
def list_grocery_transactions(
    period: str | None = None,
    membership: HouseholdMember = Depends(get_current_membership),
    db: Session = Depends(get_session),
    params: PageParams = Depends(),
) -> Page[TransactionPublic]:
    items, total = TransactionService(db).list_grocery(
        membership,
        period=period,
        limit=params.limit,
        offset=params.offset,
    )
    return Page[TransactionPublic](
        items=[TransactionPublic.model_validate(item) for item in items],
        total=total,
        limit=params.limit,
        offset=params.offset,
    )
