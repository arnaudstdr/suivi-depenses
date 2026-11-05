from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.domains.audit.models import AuditLog
from app.domains.recurring.models import RecurringExpense, RecurringOccurrence
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
from tests.finance_helpers import category_id, grocery_budget, grocery_category_id
from tests.forecast_helpers import (
    create_recurring,
    list_occurrences,
    mark_occurrence_paid,
)

pytestmark = pytest.mark.integration


def test_monthly_occurrences_are_generated_idempotently(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)
    assert login(client).status_code == 200
    recurring = create_recurring(
        client,
        category_id=category_id(client, "Logement"),
        start_date=date(2025, 1, 15),
        due_day=15,
    ).json()

    first = list_occurrences(client, recurring["id"], period="2025-01")
    second = list_occurrences(client, recurring["id"], period="2025-01")

    assert first.status_code == 200
    assert len(first.json()) == 1
    assert first.json()[0]["due_date"] == "2025-01-15"
    assert len(second.json()) == 1
    assert second.json()[0]["id"] == first.json()[0]["id"]

    february = list_occurrences(client, recurring["id"], period="2025-02")
    assert len(february.json()) == 1
    assert february.json()[0]["due_date"] == "2025-02-15"

    db_session.expire_all()
    assert len(list(db_session.scalars(select(RecurringOccurrence)).all())) == 2


def test_weekly_and_frequency_variants(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)
    assert login(client).status_code == 200
    category = category_id(client, "Loisirs")

    weekly = create_recurring(
        client,
        category_id=category,
        frequency="weekly",
        start_date=date(2025, 1, 1),
        due_day=None,
    ).json()
    weekly_dates = [
        occurrence["due_date"]
        for occurrence in list_occurrences(
            client,
            weekly["id"],
            period="2025-01",
        ).json()
    ]
    assert weekly_dates == [
        "2025-01-01",
        "2025-01-08",
        "2025-01-15",
        "2025-01-22",
        "2025-01-29",
    ]

    quarterly = create_recurring(
        client,
        category_id=category,
        frequency="quarterly",
        start_date=date(2025, 1, 31),
        due_day=31,
    ).json()
    april = list_occurrences(client, quarterly["id"], period="2025-04").json()
    july = list_occurrences(client, quarterly["id"], period="2025-07").json()
    assert april[0]["due_date"] == "2025-04-30"
    assert july[0]["due_date"] == "2025-07-31"

    yearly = create_recurring(
        client,
        category_id=category,
        frequency="yearly",
        start_date=date(2025, 3, 10),
        due_day=None,
        end_date=date(2027, 3, 10),
    ).json()
    assert len(list_occurrences(client, yearly["id"], period="2026-03").json()) == 1
    assert list_occurrences(client, yearly["id"], period="2028-03").json() == []


def test_fixed_occurrence_mark_paid_is_idempotent(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)
    assert login(client).status_code == 200
    today = date.today()
    recurring = create_recurring(
        client,
        category_id=category_id(client, "Transport"),
        label="Assurance auto",
        amount_cents=8000,
        start_date=today.replace(day=1),
        due_day=1,
    ).json()
    occurrence = list_occurrences(
        client,
        recurring["id"],
        period=today.strftime("%Y-%m"),
    ).json()[0]

    paid_at = datetime.now(UTC).isoformat()
    first = mark_occurrence_paid(
        client,
        occurrence["id"],
        paid_at=paid_at,
        payment_amount_cents=8200,
    )

    assert first.status_code == 200, first.text
    payload = first.json()
    assert payload["status"] == "paid"
    assert payload["payment_amount_cents"] == 8200
    assert payload["transaction_id"] is not None

    second = mark_occurrence_paid(client, occurrence["id"], paid_at=paid_at)
    assert second.status_code == 200
    assert second.json()["transaction_id"] == payload["transaction_id"]

    transactions = client.get("/api/v1/transactions").json()
    assert transactions["total"] == 1
    transaction = transactions["items"][0]
    assert transaction["id"] == payload["transaction_id"]
    assert transaction["recurring_occurrence_id"] == occurrence["id"]
    assert transaction["amount_cents"] == 8200

    db_session.expire_all()
    actions = set(db_session.scalars(select(AuditLog.action)).all())
    assert "recurring_occurrence.paid" in actions


def test_variable_occurrence_requires_payment_amount(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)
    assert login(client).status_code == 200
    today = date.today()
    recurring = create_recurring(
        client,
        category_id=category_id(client, "Énergie"),
        amount_cents=None,
        amount_is_variable=True,
        start_date=today.replace(day=1),
        due_day=1,
    ).json()
    occurrence = list_occurrences(
        client,
        recurring["id"],
        period=today.strftime("%Y-%m"),
    ).json()[0]

    missing = mark_occurrence_paid(client, occurrence["id"])
    assert missing.status_code == 422
    assert missing.json()["code"] == "payment_amount_required"

    paid = mark_occurrence_paid(
        client,
        occurrence["id"],
        payment_amount_cents=13550,
    )
    assert paid.status_code == 200
    assert paid.json()["payment_amount_cents"] == 13550


def test_shared_grocery_occurrence_consumes_budget(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)
    assert login(client).status_code == 200
    today = date.today()
    recurring = create_recurring(
        client,
        category_id=grocery_category_id(client),
        label="Courses récurrentes",
        amount_cents=12000,
        scope="shared",
        start_date=today.replace(day=1),
        due_day=1,
    ).json()
    occurrence = list_occurrences(
        client,
        recurring["id"],
        period=today.strftime("%Y-%m"),
    ).json()[0]

    paid = mark_occurrence_paid(client, occurrence["id"])
    assert paid.status_code == 200
    assert grocery_budget(client).json()["spent_cents"] == 12000


def test_deactivated_recurring_does_not_generate_occurrences(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)
    assert login(client).status_code == 200
    recurring = create_recurring(
        client,
        category_id=category_id(client, "Abonnements"),
        start_date=date(2025, 1, 15),
        due_day=15,
    ).json()

    deactivated = client.post(
        f"/api/v1/recurring-expenses/{recurring['id']}/deactivate",
        headers={"X-CSRF-Token": get_csrf(client)},
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False

    assert list_occurrences(client, recurring["id"], period="2025-02").json() == []

    db_session.expire_all()
    stored = db_session.get(RecurringExpense, recurring["id"])
    assert stored is not None
    assert stored.is_active is False


def test_recurring_expense_is_private_to_its_owner(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)
    assert login(client).status_code == 200
    recurring = create_recurring(
        client,
        category_id=category_id(client, "Santé"),
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

    assert client.get(f"/api/v1/recurring-expenses/{recurring['id']}").status_code == 404
    listing = client.get("/api/v1/recurring-expenses").json()
    assert recurring["id"] not in {item["id"] for item in listing["items"]}


def test_recurring_mutation_requires_csrf(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)
    assert login(client).status_code == 200

    response = client.post(
        "/api/v1/recurring-expenses",
        json={
            "label": "Sans CSRF",
            "amount_cents": 1000,
            "category_id": category_id(client, "Logement"),
            "scope": "personal",
            "frequency": "monthly",
            "start_date": date.today().isoformat(),
            "due_day": 1,
        },
    )

    assert response.status_code == 403
    assert response.json()["code"] == "csrf_failed"


def test_recurring_update_and_filters(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)
    assert login(client).status_code == 200
    recurring = create_recurring(
        client,
        category_id=category_id(client, "Logement"),
        label="Loyer",
        amount_cents=80000,
    ).json()

    updated = client.patch(
        f"/api/v1/recurring-expenses/{recurring['id']}",
        json={"label": "Loyer et charges", "amount_cents": 85000},
        headers={"X-CSRF-Token": get_csrf(client)},
    )
    assert updated.status_code == 200
    assert updated.json()["label"] == "Loyer et charges"
    assert updated.json()["amount_cents"] == 85000

    listing = client.get(
        "/api/v1/recurring-expenses",
        params={"scope": "personal", "is_active": True, "limit": 1},
    )
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert len(listing.json()["items"]) == 1
