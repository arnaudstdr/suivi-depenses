import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domains.households.models import Household, HouseholdMember
from app.domains.users.models import User


def _user(email: str = "alice@example.com") -> User:
    return User(
        id=uuid.uuid4(),
        email=email,
        password_hash="hash",
        first_name="Alice",
    )


def _household(name: str = "Foyer") -> Household:
    return Household(id=uuid.uuid4(), name=name)


@pytest.mark.integration
def test_identity_entities_can_be_persisted(db_session: Session) -> None:
    user = _user()
    household = _household()
    membership = HouseholdMember(
        id=uuid.uuid4(),
        household=household,
        user=user,
        role="owner",
    )

    db_session.add_all([user, household, membership])
    db_session.commit()

    assert db_session.get(User, user.id) is not None
    assert db_session.get(Household, household.id) is not None
    assert db_session.get(HouseholdMember, membership.id) is not None


@pytest.mark.integration
def test_email_must_be_unique(db_session: Session) -> None:
    db_session.add(_user())
    db_session.flush()

    db_session.add(_user())
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


@pytest.mark.integration
def test_email_must_be_lowercase(db_session: Session) -> None:
    db_session.add(_user(email="Alice@Example.com"))

    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


@pytest.mark.integration
def test_user_cannot_join_two_households(db_session: Session) -> None:
    user = _user()
    first = _household("Premier")
    second = _household("Second")
    db_session.add_all([user, first, second])
    db_session.flush()

    db_session.add(HouseholdMember(id=uuid.uuid4(), household=first, user=user))
    db_session.flush()
    db_session.add(HouseholdMember(id=uuid.uuid4(), household=second, user=user))

    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


@pytest.mark.integration
def test_member_role_is_validated(db_session: Session) -> None:
    user = _user()
    household = _household()
    db_session.add_all([user, household])
    db_session.flush()

    db_session.add(HouseholdMember(id=uuid.uuid4(), household=household, user=user, role="admin"))

    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()
