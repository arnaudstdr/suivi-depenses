from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.domains.audit.models import AuditLog
from app.domains.recurring.models import RecurringOccurrence
from app.domains.transactions.models import Transaction
from tests.auth_helpers import get_csrf, setup_two_member_household
from tests.finance_helpers import category_id
from tests.forecast_helpers import (
    create_planned,
    create_recurring,
    list_occurrences,
    mark_occurrence_paid,
    mark_planned_paid,
)

pytestmark = pytest.mark.integration


def _occurrence(client: TestClient, recurring_id: str, period: str) -> dict:
    response = list_occurrences(client, recurring_id, period=period)
    assert response.status_code == 200, response.text
    return response.json()[0]


def _confirm(
    client: TestClient,
    occurrence_id: str,
    amount_cents: int,
):
    return client.post(
        f"/api/v1/recurring-occurrences/{occurrence_id}/confirm-amount",
        json={"confirmed_amount_cents": amount_cents},
        headers={"X-CSRF-Token": get_csrf(client)},
    )


def _skip(client: TestClient, occurrence_id: str, reason: str | None = None):
    payload = {"reason": reason} if reason is not None else {}
    return client.post(
        f"/api/v1/recurring-occurrences/{occurrence_id}/skip",
        json=payload,
        headers={"X-CSRF-Token": get_csrf(client)},
    )


def _correct(
    client: TestClient,
    occurrence_id: str,
    *,
    amount_cents: int,
    paid_at: str,
    note: str | None = None,
):
    payload: dict[str, object] = {
        "payment_amount_cents": amount_cents,
        "paid_at": paid_at,
    }
    if note is not None:
        payload["note"] = note
    return client.post(
        f"/api/v1/recurring-occurrences/{occurrence_id}/correct-payment",
        json=payload,
        headers={"X-CSRF-Token": get_csrf(client)},
    )


def test_variable_amount_can_be_confirmed_then_paid_without_amount(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    setup_two_member_household(client, db_session, test_settings)
    recurring = create_recurring(
        client,
        category_id=category_id(client, "Énergie"),
        amount_cents=None,
        amount_is_variable=True,
        start_date=date(2025, 1, 10),
        due_day=10,
    ).json()
    occurrence = _occurrence(client, recurring["id"], "2025-01")

    confirmed = _confirm(client, occurrence["id"], 12345)
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "confirmed"
    assert confirmed.json()["confirmed_amount_cents"] == 12345
    assert confirmed.json()["confirmed_at"] is not None

    paid = mark_occurrence_paid(client, occurrence["id"], paid_at="2025-01-10T09:00:00+01:00")

    assert paid.status_code == 200, paid.text
    assert paid.json()["status"] == "paid"
    assert paid.json()["payment_amount_cents"] == 12345

    db_session.expire_all()
    transaction = db_session.scalar(
        select(Transaction).where(Transaction.recurring_occurrence_id == occurrence["id"])
    )
    assert transaction is not None
    assert transaction.amount_cents == 12345


def test_confirmation_is_refused_after_payment(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    setup_two_member_household(client, db_session, test_settings)
    recurring = create_recurring(
        client,
        category_id=category_id(client, "Loisirs"),
        amount_cents=2000,
        start_date=date(2025, 1, 10),
        due_day=10,
    ).json()
    occurrence = _occurrence(client, recurring["id"], "2025-01")
    assert (
        mark_occurrence_paid(
            client,
            occurrence["id"],
            paid_at="2025-01-10T09:00:00+01:00",
        ).status_code
        == 200
    )

    response = _confirm(client, occurrence["id"], 2500)

    assert response.status_code == 409
    assert response.json()["code"] == "occurrence_paid"


def test_skipped_occurrence_is_excluded_from_dashboard(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    setup_two_member_household(client, db_session, test_settings)
    response = client.put(
        "/api/v1/users/me/personal-balance",
        json={
            "balance_cents": 100000,
            "recorded_at": (datetime.now(UTC) - timedelta(hours=1)).isoformat(),
        },
        headers={"X-CSRF-Token": get_csrf(client)},
    )
    assert response.status_code == 201
    recurring = create_recurring(
        client,
        category_id=category_id(client, "Logement"),
        amount_cents=8000,
        start_date=date.today().replace(day=1),
        due_day=1,
    ).json()
    occurrence = _occurrence(
        client,
        recurring["id"],
        date.today().strftime("%Y-%m"),
    )

    skipped = _skip(client, occurrence["id"], "Charge reportée")
    assert skipped.status_code == 200, skipped.text
    assert skipped.json()["status"] == "skipped"
    assert skipped.json()["skip_reason"] == "Charge reportée"
    assert skipped.json()["skipped_at"] is not None

    dashboard = client.get("/api/v1/users/me/dashboard")
    assert dashboard.status_code == 200
    assert dashboard.json()["deductions"]["personal_recurring_remaining_cents"] == 0
    assert dashboard.json()["upcoming_recurring"] == []

    again = _skip(client, occurrence["id"])
    assert again.status_code == 200
    assert again.json()["status"] == "skipped"


def test_paid_occurrence_cannot_be_skipped(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    setup_two_member_household(client, db_session, test_settings)
    recurring = create_recurring(
        client,
        category_id=category_id(client, "Transport"),
        amount_cents=3000,
        start_date=date(2025, 1, 10),
        due_day=10,
    ).json()
    occurrence = _occurrence(client, recurring["id"], "2025-01")
    assert (
        mark_occurrence_paid(
            client,
            occurrence["id"],
            paid_at="2025-01-10T09:00:00+01:00",
        ).status_code
        == 200
    )

    response = _skip(client, occurrence["id"])

    assert response.status_code == 409
    assert response.json()["code"] == "occurrence_paid"


def test_paid_occurrence_correction_updates_transaction_and_audit(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    setup_two_member_household(client, db_session, test_settings)
    recurring = create_recurring(
        client,
        category_id=category_id(client, "Abonnements"),
        amount_cents=5000,
        start_date=date(2025, 1, 10),
        due_day=10,
    ).json()
    occurrence = _occurrence(client, recurring["id"], "2025-01")
    assert (
        mark_occurrence_paid(
            client,
            occurrence["id"],
            paid_at="2025-01-10T09:00:00+01:00",
        ).status_code
        == 200
    )

    corrected = _correct(
        client,
        occurrence["id"],
        amount_cents=4500,
        paid_at="2025-01-11T10:00:00+01:00",
        note="Correction du prélèvement",
    )

    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["payment_amount_cents"] == 4500
    assert datetime.fromisoformat(corrected.json()["paid_at"]) == datetime.fromisoformat(
        "2025-01-11T10:00:00+01:00"
    )

    db_session.expire_all()
    occurrence_row = db_session.get(RecurringOccurrence, occurrence["id"])
    assert occurrence_row is not None
    transaction = db_session.get(Transaction, occurrence_row.transaction_id)
    assert transaction is not None
    assert transaction.amount_cents == 4500
    assert transaction.transaction_date == date(2025, 1, 11)
    assert transaction.notes == "Correction du prélèvement"

    log = db_session.scalar(
        select(AuditLog).where(
            AuditLog.action == "recurring_occurrence.payment_corrected",
            AuditLog.entity_id == occurrence_row.id,
        )
    )
    assert log is not None
    assert log.details is not None
    assert log.details["previous_amount_cents"] == 5000
    assert log.details["amount_cents"] == 4500


def test_correction_requires_a_paid_occurrence(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    setup_two_member_household(client, db_session, test_settings)
    recurring = create_recurring(
        client,
        category_id=category_id(client, "Divers"),
        amount_cents=1000,
        start_date=date(2025, 1, 10),
        due_day=10,
    ).json()
    occurrence = _occurrence(client, recurring["id"], "2025-01")

    response = _correct(
        client,
        occurrence["id"],
        amount_cents=900,
        paid_at="2025-01-10T09:00:00+01:00",
    )

    assert response.status_code == 409
    assert response.json()["code"] == "occurrence_not_paid"


def test_linked_transaction_cannot_be_edited_or_deleted_directly(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    setup_two_member_household(client, db_session, test_settings)
    recurring = create_recurring(
        client,
        category_id=category_id(client, "Santé"),
        amount_cents=2000,
        start_date=date(2025, 1, 10),
        due_day=10,
    ).json()
    occurrence = _occurrence(client, recurring["id"], "2025-01")
    paid = mark_occurrence_paid(
        client,
        occurrence["id"],
        paid_at="2025-01-10T09:00:00+01:00",
    )
    transaction_id = paid.json()["transaction_id"]

    update = client.patch(
        f"/api/v1/transactions/{transaction_id}",
        json={"amount_cents": 1500},
        headers={"X-CSRF-Token": get_csrf(client)},
    )
    delete = client.delete(
        f"/api/v1/transactions/{transaction_id}",
        headers={"X-CSRF-Token": get_csrf(client)},
    )

    assert update.status_code == 409
    assert update.json()["code"] == "linked_transaction"
    assert delete.status_code == 409
    assert delete.json()["code"] == "linked_transaction"


def test_planned_payment_can_be_corrected_explicitly(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    setup_two_member_household(client, db_session, test_settings)
    planned = create_planned(
        client,
        category_id=category_id(client, "Loisirs"),
        amount_cents=6000,
        planned_date=date(2025, 1, 5),
    ).json()
    paid = mark_planned_paid(
        client,
        planned["id"],
        paid_at="2025-01-05T09:00:00+01:00",
    )
    assert paid.status_code == 200, paid.text

    response = client.post(
        f"/api/v1/planned-expenses/{planned['id']}/correct-payment",
        json={
            "payment_amount_cents": 5500,
            "paid_at": "2025-01-06T10:00:00+01:00",
            "note": "Montant réel",
        },
        headers={"X-CSRF-Token": get_csrf(client)},
    )

    assert response.status_code == 200, response.text
    db_session.expire_all()
    transaction = db_session.get(Transaction, paid.json()["transaction_id"])
    assert transaction is not None
    assert transaction.amount_cents == 5500
    assert transaction.transaction_date == date(2025, 1, 6)
