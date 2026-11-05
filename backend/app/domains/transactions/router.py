from datetime import date
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_membership, get_current_user, get_session, require_csrf
from app.api.pagination import Page, PageParams
from app.domains.households.models import HouseholdMember
from app.domains.transactions.models import Transaction
from app.domains.transactions.schemas import (
    TransactionCreate,
    TransactionPublic,
    TransactionUpdate,
)
from app.domains.transactions.service import TransactionService
from app.domains.users.models import User

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("", response_model=Page[TransactionPublic])
def list_transactions(
    scope: Literal["personal", "shared"] | None = None,
    category_id: UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    search: str | None = None,
    membership: HouseholdMember = Depends(get_current_membership),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
    params: PageParams = Depends(),
) -> Page[TransactionPublic]:
    items, total = TransactionService(db).list_transactions(
        membership,
        user,
        scope=scope,
        category_id=category_id,
        date_from=date_from,
        date_to=date_to,
        status=status_filter,
        search=search,
        limit=params.limit,
        offset=params.offset,
    )
    return Page[TransactionPublic](
        items=[TransactionPublic.model_validate(item) for item in items],
        total=total,
        limit=params.limit,
        offset=params.offset,
    )


@router.post("", response_model=TransactionPublic, status_code=status.HTTP_201_CREATED)
def create_transaction(
    payload: TransactionCreate,
    membership: HouseholdMember = Depends(get_current_membership),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
    _: None = Depends(require_csrf),
) -> Transaction:
    return TransactionService(db).create(membership, user, payload)


@router.get("/{transaction_id}", response_model=TransactionPublic)
def get_transaction(
    transaction_id: UUID,
    membership: HouseholdMember = Depends(get_current_membership),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> Transaction:
    return TransactionService(db).get(membership, user, transaction_id)


@router.patch("/{transaction_id}", response_model=TransactionPublic)
def update_transaction(
    transaction_id: UUID,
    payload: TransactionUpdate,
    membership: HouseholdMember = Depends(get_current_membership),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
    _: None = Depends(require_csrf),
) -> Transaction:
    return TransactionService(db).update(membership, user, transaction_id, payload)


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(
    transaction_id: UUID,
    membership: HouseholdMember = Depends(get_current_membership),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
    _: None = Depends(require_csrf),
) -> None:
    TransactionService(db).delete(membership, user, transaction_id)
