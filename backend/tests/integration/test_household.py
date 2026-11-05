import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.domains.audit.models import AuditLog
from tests.auth_helpers import bootstrap_owner, get_csrf, login

pytestmark = pytest.mark.integration


def test_household_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/households/me")

    assert response.status_code == 401
    assert response.json()["code"] == "unauthorized"


def test_owner_can_read_household(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)
    assert login(client).status_code == 200

    response = client.get("/api/v1/households/me")

    assert response.status_code == 200
    payload = response.json()
    assert payload["household"]["name"] == "Foyer test"
    assert payload["role"] == "owner"
    assert len(payload["members"]) == 1
    assert payload["members"][0]["email"] == "owner@example.com"


def test_profile_can_be_updated(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)
    assert login(client).status_code == 200
    csrf_token = get_csrf(client)

    response = client.patch(
        "/api/v1/users/me",
        json={"first_name": "Alicia"},
        headers={"X-CSRF-Token": csrf_token},
    )

    assert response.status_code == 200
    assert response.json()["first_name"] == "Alicia"
    assert client.get("/api/v1/auth/me").json()["user"]["first_name"] == "Alicia"

    db_session.expire_all()
    actions = set(db_session.scalars(select(AuditLog.action)).all())
    assert "user.profile_updated" in actions


def test_profile_update_requires_csrf(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)
    assert login(client).status_code == 200

    response = client.patch("/api/v1/users/me", json={"first_name": "Alicia"})

    assert response.status_code == 403
    assert response.json()["code"] == "csrf_failed"


def test_profile_update_requires_authentication(client: TestClient) -> None:
    response = client.patch("/api/v1/users/me", json={"first_name": "Alicia"})

    assert response.status_code == 401


def test_profile_rejects_blank_first_name(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)
    assert login(client).status_code == 200
    csrf_token = get_csrf(client)

    response = client.patch(
        "/api/v1/users/me",
        json={"first_name": "   "},
        headers={"X-CSRF-Token": csrf_token},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
