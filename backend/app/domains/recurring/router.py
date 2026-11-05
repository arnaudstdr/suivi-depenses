from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_membership, get_current_user, get_session, require_csrf
from app.api.pagination import Page, PageParams
from app.domains.households.models import HouseholdMember
from app.domains.recurring.models import RecurringExpense, RecurringOccurrence
from app.domains.recurring.schemas import (
    RecurringExpenseCreate,
    RecurringExpensePublic,
    RecurringExpenseUpdate,
    RecurringOccurrenceConfirmAmount,
    RecurringOccurrenceCorrectPayment,
    RecurringOccurrenceMarkPaid,
    RecurringOccurrencePublic,
    RecurringOccurrenceSkip,
)
from app.domains.recurring.service import RecurringService
from app.domains.users.models import User

router = APIRouter(prefix="/recurring-expenses", tags=["recurring-expenses"])
occurrences_router = APIRouter(
    prefix="/recurring-occurrences",
    tags=["recurring-occurrences"],
)


@router.get("", response_model=Page[RecurringExpensePublic])
def list_recurring_expenses(
    scope: Literal["personal", "shared"] | None = None,
    is_active: bool | None = None,
    category_id: UUID | None = None,
    membership: HouseholdMember = Depends(get_current_membership),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
    params: PageParams = Depends(),
) -> Page[RecurringExpensePublic]:
    items, total = RecurringService(db).list_recurring(
        membership,
        user,
        scope=scope,
        is_active=is_active,
        category_id=category_id,
        limit=params.limit,
        offset=params.offset,
    )
    return Page[RecurringExpensePublic](
        items=[RecurringExpensePublic.model_validate(item) for item in items],
        total=total,
        limit=params.limit,
        offset=params.offset,
    )


@router.post(
    "",
    response_model=RecurringExpensePublic,
    status_code=status.HTTP_201_CREATED,
)
def create_recurring_expense(
    payload: RecurringExpenseCreate,
    membership: HouseholdMember = Depends(get_current_membership),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
    _: None = Depends(require_csrf),
) -> RecurringExpense:
    return RecurringService(db).create(membership, user, payload)


@router.get("/{recurring_id}", response_model=RecurringExpensePublic)
def get_recurring_expense(
    recurring_id: UUID,
    membership: HouseholdMember = Depends(get_current_membership),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> RecurringExpense:
    return RecurringService(db).get(membership, user, recurring_id)


@router.patch("/{recurring_id}", response_model=RecurringExpensePublic)
def update_recurring_expense(
    recurring_id: UUID,
    payload: RecurringExpenseUpdate,
    membership: HouseholdMember = Depends(get_current_membership),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
    _: None = Depends(require_csrf),
) -> RecurringExpense:
    return RecurringService(db).update(
        membership,
        user,
        recurring_id,
        payload,
    )


@router.post("/{recurring_id}/deactivate", response_model=RecurringExpensePublic)
def deactivate_recurring_expense(
    recurring_id: UUID,
    membership: HouseholdMember = Depends(get_current_membership),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
    _: None = Depends(require_csrf),
) -> RecurringExpense:
    return RecurringService(db).deactivate(membership, user, recurring_id)


@router.get(
    "/{recurring_id}/occurrences",
    response_model=list[RecurringOccurrencePublic],
)
def list_occurrences(
    recurring_id: UUID,
    period: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    membership: HouseholdMember = Depends(get_current_membership),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> list[RecurringOccurrence]:
    return RecurringService(db).list_occurrences(
        membership,
        user,
        recurring_id,
        period=period,
        status=status_filter,
    )


@occurrences_router.post(
    "/{occurrence_id}/mark-paid",
    response_model=RecurringOccurrencePublic,
)
def mark_occurrence_paid(
    occurrence_id: UUID,
    payload: RecurringOccurrenceMarkPaid,
    membership: HouseholdMember = Depends(get_current_membership),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
    _: None = Depends(require_csrf),
) -> RecurringOccurrence:
    return RecurringService(db).mark_occurrence_paid(
        membership,
        user,
        occurrence_id,
        payload,
    )


@occurrences_router.post(
    "/{occurrence_id}/confirm-amount",
    response_model=RecurringOccurrencePublic,
)
def confirm_occurrence_amount(
    occurrence_id: UUID,
    payload: RecurringOccurrenceConfirmAmount,
    membership: HouseholdMember = Depends(get_current_membership),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
    _: None = Depends(require_csrf),
) -> RecurringOccurrence:
    return RecurringService(db).confirm_amount(
        membership,
        user,
        occurrence_id,
        payload,
    )


@occurrences_router.post(
    "/{occurrence_id}/skip",
    response_model=RecurringOccurrencePublic,
)
def skip_occurrence(
    occurrence_id: UUID,
    payload: RecurringOccurrenceSkip,
    membership: HouseholdMember = Depends(get_current_membership),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
    _: None = Depends(require_csrf),
) -> RecurringOccurrence:
    return RecurringService(db).skip_occurrence(
        membership,
        user,
        occurrence_id,
        payload,
    )


@occurrences_router.post(
    "/{occurrence_id}/correct-payment",
    response_model=RecurringOccurrencePublic,
)
def correct_occurrence_payment(
    occurrence_id: UUID,
    payload: RecurringOccurrenceCorrectPayment,
    membership: HouseholdMember = Depends(get_current_membership),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
    _: None = Depends(require_csrf),
) -> RecurringOccurrence:
    return RecurringService(db).correct_payment(
        membership,
        user,
        occurrence_id,
        payload,
    )
