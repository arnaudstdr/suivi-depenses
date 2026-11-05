from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_session, require_csrf
from app.api.pagination import Page, PageParams
from app.domains.balances.schemas import PersonalBalanceCreate, PersonalBalancePublic
from app.domains.balances.service import PersonalBalanceService
from app.domains.users.models import User

router = APIRouter(prefix="/users/me/personal-balance", tags=["balances"])


@router.get("", response_model=PersonalBalancePublic)
def get_latest_balance(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> PersonalBalancePublic:
    entry = PersonalBalanceService(db).latest(user)
    return PersonalBalancePublic.model_validate(entry)


@router.put("", response_model=PersonalBalancePublic, status_code=status.HTTP_201_CREATED)
def record_balance(
    payload: PersonalBalanceCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
    _: None = Depends(require_csrf),
) -> PersonalBalancePublic:
    entry = PersonalBalanceService(db).record(
        user,
        balance_cents=payload.balance_cents,
        recorded_at=payload.recorded_at,
        note=payload.note,
    )
    return PersonalBalancePublic.model_validate(entry)


@router.get("/history", response_model=Page[PersonalBalancePublic])
def get_balance_history(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
    params: PageParams = Depends(),
) -> Page[PersonalBalancePublic]:
    entries, total = PersonalBalanceService(db).history(
        user,
        limit=params.limit,
        offset=params.offset,
    )
    return Page[PersonalBalancePublic](
        items=[PersonalBalancePublic.model_validate(entry) for entry in entries],
        total=total,
        limit=params.limit,
        offset=params.offset,
    )
