import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domains.users.models import User


class UserRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_email(self, email: str) -> User | None:
        return self._db.scalar(select(User).where(User.email == email))

    def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return self._db.get(User, user_id)

    def add(self, user: User) -> User:
        self._db.add(user)
        return user
