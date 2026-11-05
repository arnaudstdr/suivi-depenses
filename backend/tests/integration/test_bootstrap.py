import pytest
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.domains.users.models import User
from tests.auth_helpers import bootstrap_owner

pytestmark = pytest.mark.integration


def test_bootstrap_creates_household_and_owner(
    db_session: Session,
    test_settings: Settings,
) -> None:
    user, household, membership = bootstrap_owner(db_session, test_settings)

    assert user.email == "owner@example.com"
    assert user.password_hash != "correct-horse-battery-staple"
    assert user.password_hash.startswith("$argon2id$")
    assert household.name == "Foyer test"
    assert membership.role == "owner"
    assert db_session.get(User, user.id) is not None


def test_bootstrap_rejects_second_household(
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)

    with pytest.raises(AppError) as exc_info:
        bootstrap_owner(db_session, test_settings, email="other@example.com")

    assert exc_info.value.code == "household_exists"
