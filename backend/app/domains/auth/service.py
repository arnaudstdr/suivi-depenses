import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.core.config import Settings
from app.core.errors import AppError
from app.core.request_context import request_id_var
from app.core.security import (
    generate_token,
    hash_password,
    hash_token,
    normalize_email,
    verify_dummy_password,
    verify_password,
)
from app.domains.audit.repository import AuditRepository
from app.domains.auth.models import AuthSession
from app.domains.auth.repository import AuthSessionRepository, InvitationRepository
from app.domains.households.models import HouseholdMember
from app.domains.households.repository import HouseholdRepository
from app.domains.users.models import User
from app.domains.users.repository import UserRepository


@dataclass(frozen=True)
class LoginResult:
    user: User
    auth_session: AuthSession
    raw_session_token: str
    membership: HouseholdMember


class AuthService:
    def __init__(
        self,
        db: Session,
        settings: Settings,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._db = db
        self._settings = settings
        self._now = now or utcnow
        self._users = UserRepository(db)
        self._households = HouseholdRepository(db)
        self._sessions = AuthSessionRepository(db)
        self._invitations = InvitationRepository(db)
        self._audit = AuditRepository(db)

    def login(self, email: str, password: str) -> LoginResult:
        normalized_email = normalize_email(email)
        user = self._users.get_by_email(normalized_email)

        if user is None:
            verify_dummy_password(password)
            self._record_login_failure(None)
            raise self._invalid_credentials()

        if not user.is_active or not verify_password(password, user.password_hash):
            self._record_login_failure(user.id)
            raise self._invalid_credentials()

        membership = self._households.get_membership(user.id)
        if membership is None:
            self._record_login_failure(user.id)
            raise AppError(
                code="no_household",
                message="Aucun foyer n'est associé à ce compte.",
                status_code=403,
            )

        auth_session, raw_token = self._create_session(user)
        self._audit.add(
            occurred_at=self._now(),
            action="auth.login_succeeded",
            entity_type="session",
            entity_id=auth_session.id,
            actor_user_id=user.id,
            household_id=membership.household_id,
            request_id=request_id_var.get(),
        )
        self._db.commit()

        return LoginResult(
            user=user,
            auth_session=auth_session,
            raw_session_token=raw_token,
            membership=membership,
        )

    def logout(self, auth_session: AuthSession) -> None:
        auth_session.revoked_at = self._now()
        membership = self._households.get_membership(auth_session.user_id)
        self._audit.add(
            occurred_at=self._now(),
            action="auth.logout",
            entity_type="session",
            entity_id=auth_session.id,
            actor_user_id=auth_session.user_id,
            household_id=membership.household_id if membership else None,
            request_id=request_id_var.get(),
        )
        self._db.commit()

    def accept_invitation(
        self,
        *,
        raw_token: str,
        email: str,
        first_name: str,
        password: str,
    ) -> LoginResult:
        invitation = self._invitations.get_by_token_hash_for_update(hash_token(raw_token))
        if invitation is None:
            raise self._invalid_invitation()

        now = self._now()
        normalized_email = normalize_email(email)
        if (
            invitation.used_at is not None
            or invitation.expires_at <= now
            or invitation.email != normalized_email
        ):
            raise self._invalid_invitation()

        household = self._households.get_for_update(invitation.household_id)
        if household is None:
            raise self._invalid_invitation()

        if self._households.count_active_members(household.id) >= 2:
            raise AppError(
                code="household_full",
                message="Ce foyer compte déjà deux membres.",
                status_code=409,
            )

        if self._users.get_by_email(normalized_email) is not None:
            raise AppError(
                code="email_already_registered",
                message="Un compte existe déjà avec cet email.",
                status_code=409,
            )

        cleaned_first_name = first_name.strip()
        if not cleaned_first_name:
            raise AppError(
                code="invalid_first_name",
                message="Le prénom ne peut pas être vide.",
                status_code=400,
            )

        try:
            user = User(
                email=normalized_email,
                password_hash=hash_password(password),
                first_name=cleaned_first_name,
            )
            self._users.add(user)
            self._db.flush()

            membership = HouseholdMember(
                household=household,
                user=user,
                role="member",
            )
            self._households.add_member(membership)
            self._db.flush()

            invitation.used_at = now
            invitation.accepted_by_user_id = user.id

            self._audit.add(
                occurred_at=now,
                action="invitation.accepted",
                entity_type="invitation",
                entity_id=invitation.id,
                actor_user_id=user.id,
                household_id=household.id,
                details={"role": "member"},
                request_id=request_id_var.get(),
            )

            auth_session, raw_session_token = self._create_session(user)
            self._db.commit()
        except IntegrityError:
            self._db.rollback()
            raise AppError(
                code="conflict",
                message="L'invitation ne peut plus être acceptée.",
                status_code=409,
            ) from None

        return LoginResult(
            user=user,
            auth_session=auth_session,
            raw_session_token=raw_session_token,
            membership=membership,
        )

    def _create_session(self, user: User) -> tuple[AuthSession, str]:
        now = self._now()
        raw_token = generate_token()
        auth_session = AuthSession(
            user_id=user.id,
            token_hash=hash_token(raw_token),
            created_at=now,
            last_seen_at=now,
            expires_at=now + timedelta(seconds=self._settings.session_ttl_seconds),
        )
        self._sessions.add(auth_session)
        self._db.flush()
        return auth_session, raw_token

    def _record_login_failure(self, actor_user_id: uuid.UUID | None) -> None:
        self._audit.add(
            occurred_at=self._now(),
            action="auth.login_failed",
            entity_type="session",
            actor_user_id=actor_user_id,
            details={"reason": "invalid_credentials"},
            request_id=request_id_var.get(),
        )
        self._db.commit()

    @staticmethod
    def _invalid_credentials() -> AppError:
        return AppError(
            code="invalid_credentials",
            message="Email ou mot de passe incorrect.",
            status_code=401,
        )

    @staticmethod
    def _invalid_invitation() -> AppError:
        return AppError(
            code="invalid_invitation",
            message="Cette invitation est invalide ou expirée.",
            status_code=400,
        )
