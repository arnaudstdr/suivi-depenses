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
    validate_password_strength,
)
from app.domains.audit.repository import AuditRepository
from app.domains.auth.models import Invitation
from app.domains.auth.repository import InvitationRepository
from app.domains.households.models import Household, HouseholdMember
from app.domains.households.repository import HouseholdRepository
from app.domains.users.models import User
from app.domains.users.repository import UserRepository


@dataclass(frozen=True)
class HouseholdContext:
    household: Household
    membership: HouseholdMember
    members: list[HouseholdMember]


@dataclass(frozen=True)
class InvitationCreation:
    invitation: Invitation
    raw_token: str


class HouseholdService:
    def __init__(
        self,
        db: Session,
        settings: Settings,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._db = db
        self._settings = settings
        self._now = now or utcnow
        self._households = HouseholdRepository(db)
        self._users = UserRepository(db)
        self._invitations = InvitationRepository(db)
        self._audit = AuditRepository(db)

    def get_context(self, membership: HouseholdMember) -> HouseholdContext:
        members = self._households.list_members(membership.household_id)
        return HouseholdContext(
            household=membership.household,
            membership=membership,
            members=members,
        )

    def create_invitation(
        self,
        actor: HouseholdMember,
        email: str,
    ) -> InvitationCreation:
        self._require_owner(actor)
        household = self._households.get_for_update(actor.household_id)
        if household is None:
            raise AppError(code="not_found", message="Foyer introuvable.", status_code=404)

        if self._households.count_active_members(household.id) >= 2:
            raise AppError(
                code="household_full",
                message="Ce foyer compte déjà deux membres.",
                status_code=409,
            )

        normalized_email = normalize_email(email)
        if self._users.get_by_email(normalized_email) is not None:
            raise AppError(
                code="email_already_registered",
                message="Un compte existe déjà avec cet email.",
                status_code=409,
            )

        now = self._now()
        if self._invitations.get_pending(household.id, normalized_email, now) is not None:
            raise AppError(
                code="invitation_pending",
                message="Une invitation est déjà en attente pour cet email.",
                status_code=409,
            )

        raw_token = generate_token()
        invitation = Invitation(
            household_id=household.id,
            email=normalized_email,
            role="member",
            token_hash=hash_token(raw_token),
            created_by_user_id=actor.user_id,
            created_at=now,
            expires_at=now + timedelta(seconds=self._settings.invitation_ttl_seconds),
        )
        self._invitations.add(invitation)
        self._db.flush()

        self._audit.add(
            occurred_at=now,
            action="invitation.created",
            entity_type="invitation",
            entity_id=invitation.id,
            actor_user_id=actor.user_id,
            household_id=household.id,
            details={"role": "member"},
            request_id=request_id_var.get(),
        )

        try:
            self._db.commit()
        except IntegrityError:
            self._db.rollback()
            raise AppError(
                code="conflict",
                message="Une invitation identique existe déjà.",
                status_code=409,
            ) from None

        return InvitationCreation(invitation=invitation, raw_token=raw_token)

    def list_invitations(self, actor: HouseholdMember) -> list[Invitation]:
        self._require_owner(actor)
        return self._invitations.list_for_household(actor.household_id)

    def bootstrap(
        self,
        *,
        email: str,
        first_name: str,
        household_name: str,
        password: str,
    ) -> tuple[User, Household, HouseholdMember]:
        validate_password_strength(password)
        if self._households.get_first() is not None:
            raise AppError(
                code="household_exists",
                message="Un foyer existe déjà.",
                status_code=409,
            )

        normalized_email = normalize_email(email)
        if self._users.get_by_email(normalized_email) is not None:
            raise AppError(
                code="email_already_registered",
                message="Un compte existe déjà avec cet email.",
                status_code=409,
            )

        cleaned_household_name = household_name.strip()
        if not cleaned_household_name:
            raise AppError(
                code="invalid_household_name",
                message="Le nom du foyer ne peut pas être vide.",
                status_code=400,
            )
        cleaned_first_name = first_name.strip()
        if not cleaned_first_name:
            raise AppError(
                code="invalid_first_name",
                message="Le prénom ne peut pas être vide.",
                status_code=400,
            )

        household = Household(name=cleaned_household_name)
        self._households.add(household)
        self._db.flush()

        user = User(
            email=normalized_email,
            password_hash=hash_password(password),
            first_name=cleaned_first_name,
        )
        self._users.add(user)
        self._db.flush()

        membership = HouseholdMember(
            household_id=household.id,
            user_id=user.id,
            role="owner",
        )
        self._households.add_member(membership)
        self._db.flush()

        self._audit.add(
            occurred_at=self._now(),
            action="household.bootstrapped",
            entity_type="household",
            entity_id=household.id,
            actor_user_id=user.id,
            household_id=household.id,
            request_id=request_id_var.get(),
        )
        self._db.commit()

        return user, household, membership

    @staticmethod
    def _require_owner(membership: HouseholdMember) -> None:
        if membership.role != "owner":
            raise AppError(
                code="forbidden",
                message="Seul le propriétaire du foyer peut effectuer cette action.",
                status_code=403,
            )
