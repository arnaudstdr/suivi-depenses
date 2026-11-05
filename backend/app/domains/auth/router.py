from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_app_settings,
    get_current_membership,
    get_current_session,
    get_current_user,
    get_session,
    require_csrf,
)
from app.api.presenters import auth_context_response
from app.core.config import Settings
from app.core.cookies import clear_session_cookie, set_csrf_cookie, set_session_cookie
from app.core.security import generate_token
from app.domains.auth.models import AuthSession
from app.domains.auth.schemas import CsrfResponse, InvitationAcceptRequest, LoginRequest
from app.domains.auth.service import AuthService
from app.domains.households.models import HouseholdMember
from app.domains.households.schemas import AuthContextResponse
from app.domains.households.service import HouseholdService
from app.domains.users.models import User

router = APIRouter(prefix="/auth", tags=["auth"])
invitations_router = APIRouter(prefix="/invitations", tags=["invitations"])


@router.get("/csrf", response_model=CsrfResponse)
def csrf(
    request: Request,
    response: Response,
    settings: Settings = Depends(get_app_settings),
) -> CsrfResponse:
    token = request.cookies.get(settings.csrf_cookie_name)
    if not token or len(token) < 32:
        token = generate_token()
    set_csrf_cookie(response, token, settings)
    return CsrfResponse(csrf_token=token)


@router.post("/login", response_model=AuthContextResponse)
def login(
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_session),
    settings: Settings = Depends(get_app_settings),
    _: None = Depends(require_csrf),
) -> AuthContextResponse:
    result = AuthService(db, settings).login(str(payload.email), payload.password)
    set_session_cookie(response, result.raw_session_token, settings)
    context = HouseholdService(db, settings).get_context(result.membership)
    return auth_context_response(result.user, context)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    auth_session: AuthSession = Depends(get_current_session),
    db: Session = Depends(get_session),
    settings: Settings = Depends(get_app_settings),
    _: None = Depends(require_csrf),
) -> None:
    AuthService(db, settings).logout(auth_session)
    clear_session_cookie(response, settings)
    response.status_code = status.HTTP_204_NO_CONTENT


@router.get("/me", response_model=AuthContextResponse)
def me(
    user: User = Depends(get_current_user),
    membership: HouseholdMember = Depends(get_current_membership),
    db: Session = Depends(get_session),
    settings: Settings = Depends(get_app_settings),
) -> AuthContextResponse:
    context = HouseholdService(db, settings).get_context(membership)
    return auth_context_response(user, context)


@invitations_router.post(
    "/{token}/accept",
    response_model=AuthContextResponse,
    status_code=status.HTTP_201_CREATED,
)
def accept_invitation(
    token: str,
    payload: InvitationAcceptRequest,
    response: Response,
    db: Session = Depends(get_session),
    settings: Settings = Depends(get_app_settings),
    _: None = Depends(require_csrf),
) -> AuthContextResponse:
    result = AuthService(db, settings).accept_invitation(
        raw_token=token,
        email=str(payload.email),
        first_name=payload.first_name,
        password=payload.password,
    )
    set_session_cookie(response, result.raw_session_token, settings)
    context = HouseholdService(db, settings).get_context(result.membership)
    return auth_context_response(result.user, context)
