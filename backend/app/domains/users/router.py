from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_session, require_csrf
from app.api.presenters import user_public
from app.domains.users.models import User
from app.domains.users.schemas import UserPublic, UserUpdate
from app.domains.users.service import UserService

router = APIRouter(prefix="/users", tags=["users"])


@router.patch("/me", response_model=UserPublic)
def update_me(
    payload: UserUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
    _: None = Depends(require_csrf),
) -> UserPublic:
    updated = UserService(db).update_profile(user, payload.first_name)
    return user_public(updated)
