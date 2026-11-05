from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.domains.audit.models import AuditLog
from app.domains.auth.models import AuthSession
from tests.auth_helpers import (
    OWNER_EMAIL,
    OWNER_PASSWORD,
    bootstrap_owner,
    get_csrf,
    login,
)

pytestmark = pytest.mark.integration


def test_login_requires_csrf(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)

    response = client.post(
        "/api/v1/auth/login",
        json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD},
    )

    assert response.status_code == 403
    assert response.json()["code"] == "csrf_failed"


def test_login_success_and_me(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)

    response = login(client)

    assert response.status_code == 200
    payload = response.json()
    assert payload["user"]["email"] == OWNER_EMAIL
    assert payload["household"]["name"] == "Foyer test"
    assert payload["role"] == "owner"
    assert payload["members"][0]["role"] == "owner"

    set_cookie = response.headers.get("set-cookie", "").lower()
    assert "httponly" in set_cookie
    assert "samesite=lax" in set_cookie

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["email"] == OWNER_EMAIL
    assert me.headers["cache-control"] == "no-store"

    raw_session_token = client.cookies.get("suivi_session")
    assert raw_session_token is not None
    db_session.expire_all()
    auth_session = db_session.scalar(select(AuthSession))
    assert auth_session is not None
    assert len(auth_session.token_hash) == 64
    assert auth_session.token_hash != raw_session_token


def test_login_with_wrong_password_is_generic_and_audited(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)

    response = login(client, password="wrong-password")

    assert response.status_code == 401
    assert response.json()["code"] == "invalid_credentials"
    assert response.json()["message"] == "Email ou mot de passe incorrect."

    db_session.expire_all()
    actions = set(db_session.scalars(select(AuditLog.action)).all())
    assert "auth.login_failed" in actions


def test_inactive_user_cannot_login(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    user, _, _ = bootstrap_owner(db_session, test_settings)
    user.is_active = False
    db_session.commit()

    response = login(client)

    assert response.status_code == 401
    assert response.json()["code"] == "invalid_credentials"


def test_logout_revokes_session(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)
    assert login(client).status_code == 200

    csrf_token = get_csrf(client)
    response = client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": csrf_token},
    )

    assert response.status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401

    db_session.expire_all()
    auth_session = db_session.scalar(select(AuthSession))
    assert auth_session is not None
    assert auth_session.revoked_at is not None


def test_logout_requires_csrf(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)
    assert login(client).status_code == 200

    response = client.post("/api/v1/auth/logout")

    assert response.status_code == 403
    assert response.json()["code"] == "csrf_failed"
    assert client.get("/api/v1/auth/me").status_code == 200


def test_expired_session_is_rejected(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)
    assert login(client).status_code == 200

    now = datetime.now(UTC)
    db_session.execute(
        update(AuthSession).values(
            created_at=now - timedelta(hours=2),
            expires_at=now - timedelta(hours=1),
        )
    )
    db_session.commit()

    assert client.get("/api/v1/auth/me").status_code == 401


def test_me_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.json()["code"] == "unauthorized"


def test_csrf_token_is_stable(client: TestClient) -> None:
    first = client.get("/api/v1/auth/csrf")
    second = client.get("/api/v1/auth/csrf")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["csrf_token"] == second.json()["csrf_token"]
    assert "suivi_csrf" in first.headers.get("set-cookie", "")
