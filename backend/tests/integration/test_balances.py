import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.domains.audit.models import AuditLog
from tests.auth_helpers import (
    INVITEE_EMAIL,
    INVITEE_FIRST_NAME,
    INVITEE_PASSWORD,
    accept_invitation,
    bootstrap_owner,
    create_invitation,
    get_csrf,
    login,
)

pytestmark = pytest.mark.integration


def _record(
    client: TestClient,
    *,
    balance_cents: int,
    recorded_at: str | None = None,
    note: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {"balance_cents": balance_cents}
    if recorded_at is not None:
        payload["recorded_at"] = recorded_at
    if note is not None:
        payload["note"] = note
    response = client.put(
        "/api/v1/users/me/personal-balance",
        json=payload,
        headers={"X-CSRF-Token": get_csrf(client)},
    )
    assert response.status_code == 201, response.text
    return dict(response.json())


def test_balance_requires_authentication(client: TestClient) -> None:
    assert client.get("/api/v1/users/me/personal-balance").status_code == 401
    assert (
        client.put("/api/v1/users/me/personal-balance", json={"balance_cents": 1}).status_code
        == 401
    )


def test_balance_requires_csrf(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)
    assert login(client).status_code == 200

    response = client.put(
        "/api/v1/users/me/personal-balance",
        json={"balance_cents": 1000},
    )

    assert response.status_code == 403
    assert response.json()["code"] == "csrf_failed"


def test_record_and_read_latest_balance(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)
    assert login(client).status_code == 200

    missing = client.get("/api/v1/users/me/personal-balance")
    assert missing.status_code == 404
    assert missing.json()["code"] == "balance_not_found"

    first = _record(client, balance_cents=150000, recorded_at="2026-11-05T08:30:00+01:00")
    second = _record(client, balance_cents=-2500, note="Découvert")

    latest = client.get("/api/v1/users/me/personal-balance")
    assert latest.status_code == 200
    assert latest.json()["id"] == second["id"]
    assert latest.json()["balance_cents"] == -2500
    assert latest.json()["note"] == "Découvert"

    history = client.get("/api/v1/users/me/personal-balance/history")
    assert history.status_code == 200
    assert history.json()["total"] == 2
    assert history.json()["items"][0]["id"] == second["id"]
    assert first["id"] != second["id"]

    db_session.expire_all()
    actions = set(db_session.scalars(select(AuditLog.action)).all())
    assert "balance.recorded" in actions


def test_balance_history_is_paginated(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)
    assert login(client).status_code == 200
    for day in range(1, 4):
        _record(
            client,
            balance_cents=day * 1000,
            recorded_at=f"2026-11-0{day}T08:00:00+01:00",
        )

    response = client.get(
        "/api/v1/users/me/personal-balance/history",
        params={"limit": 2, "offset": 1},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 3
    assert payload["limit"] == 2
    assert payload["offset"] == 1
    assert len(payload["items"]) == 2


def test_balance_is_scoped_to_the_current_user(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)
    assert login(client).status_code == 200
    _record(client, balance_cents=1000)
    invitation = create_invitation(client, email=INVITEE_EMAIL)

    client.cookies.clear()
    assert (
        accept_invitation(
            client,
            token=invitation.json()["token"],
            email=INVITEE_EMAIL,
            first_name=INVITEE_FIRST_NAME,
            password=INVITEE_PASSWORD,
        ).status_code
        == 201
    )

    # La route est toujours celle de l'utilisateur connecté : le second membre
    # ne voit pas le solde du propriétaire.
    assert client.get("/api/v1/users/me/personal-balance").status_code == 404
