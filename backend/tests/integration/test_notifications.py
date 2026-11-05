import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import Settings
from tests.auth_helpers import get_csrf, login, setup_two_member_household

pytestmark = pytest.mark.integration

CSV_HEADER = "date,label,amount,category,notes\n"


def _notifications(client: TestClient, *, unread_only: bool = False) -> list[dict]:
    response = client.get(
        "/api/v1/notifications",
        params={"unread_only": unread_only},
    )
    assert response.status_code == 200, response.text
    return response.json()["items"]


def _update_preferences(client: TestClient, preferences: list[dict]):
    return client.put(
        "/api/v1/notifications/preferences",
        json={"preferences": preferences},
        headers={"X-CSRF-Token": get_csrf(client)},
    )


def _import_one(client: TestClient) -> dict:
    content = (CSV_HEADER + "2025-01-10,Café,4.50,Loisirs,\n").encode()
    preview = client.post(
        "/api/v1/imports/transactions/preview",
        files={"file": ("depenses.csv", content, "text/csv")},
        data={"scope": "personal"},
        headers={"X-CSRF-Token": get_csrf(client)},
    )
    assert preview.status_code == 200, preview.text
    validated = client.post(
        f"/api/v1/imports/{preview.json()['id']}/validate",
        json={"duplicate_policy": "skip"},
        headers={"X-CSRF-Token": get_csrf(client)},
    )
    assert validated.status_code == 200, validated.text
    return validated.json()


def test_invitation_acceptance_creates_owner_notification(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    setup_two_member_household(client, db_session, test_settings)

    rows = _notifications(client)

    assert len(rows) == 1
    assert rows[0]["type"] == "invitation_accepted"
    assert rows[0]["read_at"] is None
    assert client.get("/api/v1/notifications/unread-count").json() == {"count": 1}


def test_notification_can_be_marked_read_and_read_all(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    setup_two_member_household(client, db_session, test_settings)
    notification = _notifications(client)[0]

    marked = client.post(
        f"/api/v1/notifications/{notification['id']}/read",
        headers={"X-CSRF-Token": get_csrf(client)},
    )

    assert marked.status_code == 200, marked.text
    assert marked.json()["read_at"] is not None
    assert client.get("/api/v1/notifications/unread-count").json() == {"count": 0}
    assert len(_notifications(client, unread_only=True)) == 0

    _import_one(client)
    assert client.get("/api/v1/notifications/unread-count").json()["count"] == 1

    read_all = client.post(
        "/api/v1/notifications/read-all",
        headers={"X-CSRF-Token": get_csrf(client)},
    )
    assert read_all.status_code == 200
    assert client.get("/api/v1/notifications/unread-count").json() == {"count": 0}


def test_notification_is_private_to_its_recipient(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    setup_two_member_household(client, db_session, test_settings)
    notification = _notifications(client)[0]

    client.cookies.clear()
    assert (
        login(
            client,
            email="member@example.com",
            password="another-strong-password",
        ).status_code
        == 200
    )

    response = client.post(
        f"/api/v1/notifications/{notification['id']}/read",
        headers={"X-CSRF-Token": get_csrf(client)},
    )

    assert response.status_code == 404


def test_preferences_defaults_and_update(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    setup_two_member_household(client, db_session, test_settings)

    defaults = client.get("/api/v1/notifications/preferences")

    assert defaults.status_code == 200
    assert {item["type"] for item in defaults.json()} == {
        "invitation_accepted",
        "import_completed",
    }
    assert all(item["in_app_enabled"] for item in defaults.json())
    assert all(not item["push_enabled"] for item in defaults.json())

    updated = _update_preferences(
        client,
        [
            {
                "type": "import_completed",
                "in_app_enabled": False,
                "push_enabled": False,
            }
        ],
    )

    assert updated.status_code == 200, updated.text
    preference = next(item for item in updated.json() if item["type"] == "import_completed")
    assert preference["in_app_enabled"] is False


def test_disabled_notification_type_is_not_created(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    setup_two_member_household(client, db_session, test_settings)
    assert (
        _update_preferences(
            client,
            [
                {
                    "type": "import_completed",
                    "in_app_enabled": False,
                    "push_enabled": False,
                }
            ],
        ).status_code
        == 200
    )

    _import_one(client)

    assert all(row["type"] != "import_completed" for row in _notifications(client))


def test_invalid_notification_preference_is_rejected(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    setup_two_member_household(client, db_session, test_settings)

    response = _update_preferences(
        client,
        [
            {
                "type": "unknown_type",
                "in_app_enabled": True,
                "push_enabled": False,
            }
        ],
    )

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_notification_type"


def test_notification_mutations_require_csrf(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    setup_two_member_household(client, db_session, test_settings)
    notification = _notifications(client)[0]

    read = client.post(f"/api/v1/notifications/{notification['id']}/read")
    preferences = client.put(
        "/api/v1/notifications/preferences",
        json={
            "preferences": [
                {
                    "type": "import_completed",
                    "in_app_enabled": True,
                    "push_enabled": False,
                }
            ]
        },
    )

    assert read.status_code == 403
    assert preferences.status_code == 403
