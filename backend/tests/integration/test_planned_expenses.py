from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.domains.audit.models import AuditLog
from app.domains.planned.models import PlannedExpense
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
from tests.finance_helpers import (
    category_id,
    grocery_budget,
    grocery_category_id,
)
from tests.forecast_helpers import create_planned, mark_planned_paid

pytestmark = pytest.mark.integration


def test_planned_expense_lifecycle(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)
    assert login(client).status_code == 200
    transport_id = category_id(client, "Transport")

    created = create_planned(
        client,
        category_id=transport_id,
        label="Révision voiture",
        amount_cents=25000,
        planned_date=date.today(),
        status="committed",
    )
    assert created.status_code == 201, created.text
    payload = created.json()
    assert payload["status"] == "committed"
    assert payload["scope"] == "personal"
    assert payload["transaction_id"] is None

    listing = client.get("/api/v1/planned-expenses")
    assert listing.status_code == 200
    assert listing.json()["total"] == 1

    updated = client.patch(
        f"/api/v1/planned-expenses/{payload['id']}",
        json={"label": "Révision et pneus", "status": "planned"},
        headers={"X-CSRF-Token": get_csrf(client)},
    )
    assert updated.status_code == 200
    assert updated.json()["label"] == "Révision et pneus"
    assert updated.json()["status"] == "planned"

    paid = mark_planned_paid(
        client,
        payload["id"],
        paid_at="2026-11-05T10:00:00+01:00",
        payment_amount_cents=24000,
    )
    assert paid.status_code == 200, paid.text
    assert paid.json()["status"] == "paid"
    assert paid.json()["transaction_id"] is not None

    again = mark_planned_paid(client, payload["id"])
    assert again.status_code == 200
    assert again.json()["transaction_id"] == paid.json()["transaction_id"]

    transactions = client.get("/api/v1/transactions").json()
    assert transactions["total"] == 1
    assert transactions["items"][0]["amount_cents"] == 24000
    assert transactions["items"][0]["id"] == paid.json()["transaction_id"]

    db_session.expire_all()
    actions = set(db_session.scalars(select(AuditLog.action)).all())
    assert {"planned.created", "planned.updated", "planned.paid"} <= actions


def test_planned_expense_can_be_cancelled(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)
    assert login(client).status_code == 200
    created = create_planned(
        client,
        category_id=category_id(client, "Loisirs"),
        amount_cents=3000,
    ).json()

    cancelled = client.delete(
        f"/api/v1/planned-expenses/{created['id']}",
        headers={"X-CSRF-Token": get_csrf(client)},
    )
    assert cancelled.status_code == 204
    assert client.get(f"/api/v1/planned-expenses/{created['id']}").json()["status"] == "cancelled"

    invalid_payment = mark_planned_paid(client, created["id"])
    assert invalid_payment.status_code == 409
    assert invalid_payment.json()["code"] == "planned_cancelled"

    db_session.expire_all()
    stored = db_session.get(PlannedExpense, created["id"])
    assert stored is not None
    assert stored.status == "cancelled"


def test_shared_grocery_planned_expense_consumes_budget_when_paid(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)
    assert login(client).status_code == 200
    planned = create_planned(
        client,
        category_id=grocery_category_id(client),
        label="Courses prévues",
        amount_cents=7000,
        scope="shared",
    ).json()

    assert grocery_budget(client).json()["spent_cents"] == 0
    assert mark_planned_paid(client, planned["id"]).status_code == 200
    assert grocery_budget(client).json()["spent_cents"] == 7000


def test_planned_expense_is_private_to_its_owner(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)
    assert login(client).status_code == 200
    planned = create_planned(
        client,
        category_id=category_id(client, "Transport"),
    ).json()
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

    assert client.get(f"/api/v1/planned-expenses/{planned['id']}").status_code == 404
    listing = client.get("/api/v1/planned-expenses").json()
    assert planned["id"] not in {item["id"] for item in listing["items"]}


def test_planned_expense_mutation_requires_csrf(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)
    assert login(client).status_code == 200

    response = client.post(
        "/api/v1/planned-expenses",
        json={
            "label": "Sans CSRF",
            "amount_cents": 1000,
            "planned_date": date.today().isoformat(),
            "category_id": category_id(client, "Transport"),
            "scope": "personal",
        },
    )

    assert response.status_code == 403
    assert response.json()["code"] == "csrf_failed"


def test_planned_expense_filters_and_pagination(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)
    assert login(client).status_code == 200
    transport_id = category_id(client, "Transport")
    for index in range(3):
        response = create_planned(
            client,
            category_id=transport_id,
            label=f"Prévu {index}",
            amount_cents=1000 + index,
            planned_date=date.today(),
        )
        assert response.status_code == 201

    response = client.get(
        "/api/v1/planned-expenses",
        params={"status": "planned", "limit": 2, "offset": 0},
    )

    assert response.status_code == 200
    assert response.json()["total"] == 3
    assert len(response.json()["items"]) == 2
