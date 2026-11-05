import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.domains.audit.models import AuditLog
from tests.auth_helpers import bootstrap_owner, get_csrf, login
from tests.finance_helpers import create_category, grocery_category_id, list_categories

pytestmark = pytest.mark.integration


def test_default_categories_are_available_after_bootstrap(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)
    assert login(client).status_code == 200

    categories = list_categories(client)

    assert len(categories) == 9
    assert len([category for category in categories if category["is_grocery"]]) == 1
    assert all(category["household_id"] is None for category in categories)
    assert grocery_category_id(client)


def test_create_and_update_household_category(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)
    assert login(client).status_code == 200

    created = create_category(client, name="Animaux", icon="paw-print")
    assert created.status_code == 201
    payload = created.json()
    assert payload["name"] == "Animaux"
    assert payload["household_id"] is not None

    updated = client.patch(
        f"/api/v1/categories/{payload['id']}",
        json={"name": "Animaux et vétérinaire", "icon": "dog"},
        headers={"X-CSRF-Token": get_csrf(client)},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Animaux et vétérinaire"
    assert updated.json()["icon"] == "dog"

    deactivated = client.patch(
        f"/api/v1/categories/{payload['id']}",
        json={"is_active": False},
        headers={"X-CSRF-Token": get_csrf(client)},
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False
    assert payload["id"] not in {category["id"] for category in list_categories(client)}

    db_session.expire_all()
    actions = set(db_session.scalars(select(AuditLog.action)).all())
    assert {"category.created", "category.updated"} <= actions


def test_category_name_must_be_unique(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)
    assert login(client).status_code == 200
    assert create_category(client, name="Animaux").status_code == 201

    duplicate = create_category(client, name="animaux")

    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "category_exists"

    global_duplicate = create_category(client, name="Transport")
    assert global_duplicate.status_code == 409


def test_global_category_cannot_be_modified(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)
    assert login(client).status_code == 200
    transport_id = next(
        category["id"] for category in list_categories(client) if category["name"] == "Transport"
    )

    response = client.patch(
        f"/api/v1/categories/{transport_id}",
        json={"name": "Transport modifié"},
        headers={"X-CSRF-Token": get_csrf(client)},
    )

    assert response.status_code == 404


def test_category_mutation_requires_csrf(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)
    assert login(client).status_code == 200

    response = client.post("/api/v1/categories", json={"name": "Sans CSRF"})

    assert response.status_code == 403
    assert response.json()["code"] == "csrf_failed"
