from datetime import date
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_membership, get_current_user, get_session, require_csrf
from app.api.pagination import Page, PageParams
from app.domains.households.models import HouseholdMember
from app.domains.planned.models import PlannedExpense
from app.domains.planned.schemas import (
    PlannedExpenseCorrectPayment,
    PlannedExpenseCreate,
    PlannedExpenseMarkPaid,
    PlannedExpensePublic,
    PlannedExpenseUpdate,
)
from app.domains.planned.service import PlannedExpenseService
from app.domains.users.models import User

router = APIRouter(prefix="/planned-expenses", tags=["planned-expenses"])


@router.get("", response_model=Page[PlannedExpensePublic])
def list_planned_expenses(
    scope: Literal["personal", "shared"] | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    category_id: UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    membership: HouseholdMember = Depends(get_current_membership),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
    params: PageParams = Depends(),
) -> Page[PlannedExpensePublic]:
    items, total = PlannedExpenseService(db).list(
        membership,
        user,
        scope=scope,
        status=status_filter,
        category_id=category_id,
        date_from=date_from,
        date_to=date_to,
        limit=params.limit,
        offset=params.offset,
    )
    return Page[PlannedExpensePublic](
        items=[PlannedExpensePublic.model_validate(item) for item in items],
        total=total,
        limit=params.limit,
        offset=params.offset,
    )


@router.post("", response_model=PlannedExpensePublic, status_code=status.HTTP_201_CREATED)
def create_planned_expense(
    payload: PlannedExpenseCreate,
    membership: HouseholdMember = Depends(get_current_membership),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
    _: None = Depends(require_csrf),
) -> PlannedExpense:
    return PlannedExpenseService(db).create(membership, user, payload)


@router.get("/{planned_id}", response_model=PlannedExpensePublic)
def get_planned_expense(
    planned_id: UUID,
    membership: HouseholdMember = Depends(get_current_membership),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> PlannedExpense:
    return PlannedExpenseService(db).get(membership, user, planned_id)


@router.patch("/{planned_id}", response_model=PlannedExpensePublic)
def update_planned_expense(
    planned_id: UUID,
    payload: PlannedExpenseUpdate,
    membership: HouseholdMember = Depends(get_current_membership),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
    _: None = Depends(require_csrf),
) -> PlannedExpense:
    return PlannedExpenseService(db).update(membership, user, planned_id, payload)


@router.post("/{planned_id}/mark-paid", response_model=PlannedExpensePublic)
def mark_planned_expense_paid(
    planned_id: UUID,
    payload: PlannedExpenseMarkPaid,
    membership: HouseholdMember = Depends(get_current_membership),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
    _: None = Depends(require_csrf),
) -> PlannedExpense:
    return PlannedExpenseService(db).mark_paid(membership, user, planned_id, payload)


@router.post("/{planned_id}/correct-payment", response_model=PlannedExpensePublic)
def correct_planned_expense_payment(
    planned_id: UUID,
    payload: PlannedExpenseCorrectPayment,
    membership: HouseholdMember = Depends(get_current_membership),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
    _: None = Depends(require_csrf),
) -> PlannedExpense:
    return PlannedExpenseService(db).correct_payment(
        membership,
        user,
        planned_id,
        payload,
    )


@router.delete("/{planned_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_planned_expense(
    planned_id: UUID,
    membership: HouseholdMember = Depends(get_current_membership),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
    _: None = Depends(require_csrf),
) -> None:
    PlannedExpenseService(db).cancel(membership, user, planned_id)
