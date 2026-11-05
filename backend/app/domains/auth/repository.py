import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.domains.auth.models import AuthSession, Invitation


class AuthSessionRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_token_hash(self, token_hash: str) -> AuthSession | None:
        return self._db.scalar(
            select(AuthSession)
            .options(joinedload(AuthSession.user))
            .where(AuthSession.token_hash == token_hash)
        )

    def add(self, auth_session: AuthSession) -> AuthSession:
        self._db.add(auth_session)
        return auth_session


class InvitationRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_token_hash_for_update(self, token_hash: str) -> Invitation | None:
        return self._db.scalar(
            select(Invitation).where(Invitation.token_hash == token_hash).with_for_update()
        )

    def get_pending(
        self,
        household_id: uuid.UUID,
        email: str,
        now: datetime,
    ) -> Invitation | None:
        return self._db.scalar(
            select(Invitation).where(
                Invitation.household_id == household_id,
                Invitation.email == email,
                Invitation.used_at.is_(None),
                Invitation.expires_at > now,
            )
        )

    def list_for_household(self, household_id: uuid.UUID) -> list[Invitation]:
        return list(
            self._db.scalars(
                select(Invitation)
                .where(Invitation.household_id == household_id)
                .order_by(Invitation.created_at.desc())
            ).all()
        )

    def add(self, invitation: Invitation) -> Invitation:
        self._db.add(invitation)
        return invitation
