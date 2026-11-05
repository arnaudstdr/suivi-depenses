from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.domains.audit.models import AuditLog
from app.domains.auth.models import Invitation
from app.domains.households.models import HouseholdMember
from app.domains.households.service import HouseholdService
from app.domains.users.models import User
from tests.auth_helpers import (
    INVITEE_EMAIL,
    INVITEE_FIRST_NAME,
    INVITEE_PASSWORD,
    OWNER_EMAIL,
    accept_invitation,
    bootstrap_owner,
    create_invitation,
    get_csrf,
    login,
)

pytestmark = pytest.mark.integration


def test_owner_creates_invitation_and_member_accepts(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)
    assert login(client).status_code == 200

    response = create_invitation(client)

    assert response.status_code == 201
    payload = response.json()
    token = payload["token"]
    assert payload["email"] == INVITEE_EMAIL
    assert payload["role"] == "member"
    assert payload["accept_path"].endswith(f"/invitations/{token}/accept")

    db_session.expire_all()
    invitation = db_session.scalar(select(Invitation))
    assert invitation is not None
    assert invitation.token_hash != token
    assert invitation.used_at is None

    listing = client.get("/api/v1/households/me/invitations")
    assert listing.status_code == 200
    assert len(listing.json()) == 1
    assert "token" not in listing.json()[0]

    client.cookies.clear()
    accepted = accept_invitation(client, token=token)

    assert accepted.status_code == 201
    assert accepted.json()["user"]["email"] == INVITEE_EMAIL
    assert accepted.json()["role"] == "member"
    assert len(accepted.json()["members"]) == 2
    assert "httponly" in accepted.headers.get("set-cookie", "").lower()

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["role"] == "member"

    db_session.expire_all()
    member_user = db_session.scalar(select(User).where(User.email == INVITEE_EMAIL))
    assert member_user is not None
    member = db_session.scalar(
        select(HouseholdMember).where(HouseholdMember.user_id == member_user.id)
    )
    assert member is not None
    assert member.role == "member"

    logs = list(db_session.scalars(select(AuditLog)).all())
    actions = {log.action for log in logs}
    assert {"invitation.created", "invitation.accepted"} <= actions
    assert all(token not in str(log.details) for log in logs)
    assert all("correct-horse-battery-staple" not in str(log.details) for log in logs)

    client.cookies.clear()
    reused = accept_invitation(client, token=token)

    assert reused.status_code == 400
    assert reused.json()["code"] == "invalid_invitation"


def test_invitation_email_must_match(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)
    assert login(client).status_code == 200
    token = create_invitation(client).json()["token"]

    client.cookies.clear()
    response = accept_invitation(client, token=token, email="autre@example.com")

    assert response.status_code == 400
    assert response.json()["code"] == "invalid_invitation"


def test_expired_invitation_is_rejected(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    _, _, membership = bootstrap_owner(db_session, test_settings)
    past = datetime.now(UTC) - timedelta(days=30)
    creation = HouseholdService(
        db_session,
        test_settings,
        now=lambda: past,
    ).create_invitation(membership, INVITEE_EMAIL)

    response = accept_invitation(client, token=creation.raw_token)

    assert response.status_code == 400
    assert response.json()["code"] == "invalid_invitation"


def test_household_full_is_rejected(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)
    assert login(client).status_code == 200
    token = create_invitation(client).json()["token"]

    client.cookies.clear()
    assert accept_invitation(client, token=token).status_code == 201

    client.cookies.clear()
    assert login(client).status_code == 200
    response = create_invitation(client, email="third@example.com")

    assert response.status_code == 409
    assert response.json()["code"] == "household_full"


def test_member_cannot_create_invitation(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)
    assert login(client).status_code == 200
    token = create_invitation(client).json()["token"]

    client.cookies.clear()
    assert accept_invitation(client, token=token).status_code == 201

    response = create_invitation(client, email="third@example.com")

    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"


def test_invitation_for_existing_email_is_rejected(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)
    assert login(client).status_code == 200

    response = create_invitation(client, email=OWNER_EMAIL)

    assert response.status_code == 409
    assert response.json()["code"] == "email_already_registered"


def test_pending_invitation_is_rejected(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)
    assert login(client).status_code == 200
    assert create_invitation(client).status_code == 201

    response = create_invitation(client)

    assert response.status_code == 409
    assert response.json()["code"] == "invitation_pending"


def test_create_invitation_requires_csrf(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)
    assert login(client).status_code == 200

    response = client.post(
        "/api/v1/households/me/invitations",
        json={"email": INVITEE_EMAIL},
    )

    assert response.status_code == 403
    assert response.json()["code"] == "csrf_failed"


def test_accept_invitation_requires_csrf(client: TestClient) -> None:
    response = client.post(
        "/api/v1/invitations/invalid-token/accept",
        json={
            "email": INVITEE_EMAIL,
            "first_name": INVITEE_FIRST_NAME,
            "password": INVITEE_PASSWORD,
        },
    )

    assert response.status_code == 403
    assert response.json()["code"] == "csrf_failed"


def test_csrf_cookie_is_available_before_login(client: TestClient) -> None:
    token = get_csrf(client)

    assert len(token) >= 32
