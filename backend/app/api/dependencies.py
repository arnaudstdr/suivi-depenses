from collections.abc import Iterator
from typing import Final

from fastapi import Depends, Request
from sqlalchemy.orm import Session, sessionmaker

from app.core.clock import utcnow
from app.core.config import Settings
from app.core.errors import AppError
from app.core.security import constant_time_compare, hash_token
from app.domains.auth.models import AuthSession
from app.domains.auth.repository import AuthSessionRepository
from app.domains.households.models import HouseholdMember
from app.domains.households.repository import HouseholdRepository
from app.domains.users.models import User

CSRF_HEADER_NAME: Final = "X-CSRF-Token"


def get_session(request: Request) -> Iterator[Session]:
    """Fournit une session SQLAlchemy par requête, fermée automatiquement."""
    factory: sessionmaker[Session] = request.app.state.session_factory
    with factory() as session:
        yield session


def get_app_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_current_session(
    request: Request,
    db: Session = Depends(get_session),
    settings: Settings = Depends(get_app_settings),
) -> AuthSession:
    raw_token = request.cookies.get(settings.session_cookie_name)
    if not raw_token:
        raise _unauthorized()

    auth_session = AuthSessionRepository(db).get_by_token_hash(hash_token(raw_token))
    if auth_session is None:
        raise _unauthorized()
    if auth_session.revoked_at is not None:
        raise _unauthorized()
    if auth_session.expires_at <= utcnow():
        raise _unauthorized()
    if not auth_session.user.is_active:
        raise _unauthorized()

    return auth_session


def get_current_user(auth_session: AuthSession = Depends(get_current_session)) -> User:
    return auth_session.user


def get_current_membership(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> HouseholdMember:
    membership = HouseholdRepository(db).get_membership(user.id)
    if membership is None:
        raise AppError(
            code="no_household",
            message="Aucun foyer actif n'est associé à ce compte.",
            status_code=403,
        )
    return membership


def require_owner(
    membership: HouseholdMember = Depends(get_current_membership),
) -> HouseholdMember:
    if membership.role != "owner":
        raise AppError(
            code="forbidden",
            message="Seul le propriétaire du foyer peut effectuer cette action.",
            status_code=403,
        )
    return membership


def require_csrf(
    request: Request,
    settings: Settings = Depends(get_app_settings),
) -> None:
    cookie_token = request.cookies.get(settings.csrf_cookie_name)
    header_token = request.headers.get(CSRF_HEADER_NAME)
    if (
        not cookie_token
        or not header_token
        or not constant_time_compare(cookie_token, header_token)
    ):
        raise AppError(
            code="csrf_failed",
            message="Jeton CSRF invalide ou absent.",
            status_code=403,
        )


def _unauthorized() -> AppError:
    return AppError(
        code="unauthorized",
        message="Authentification requise.",
        status_code=401,
    )
