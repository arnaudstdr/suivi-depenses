from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.periods import current_period, parse_period
from app.domains.recurring.models import RecurringOccurrence
from app.domains.recurring.service import RecurringService
from tests.auth_helpers import get_csrf, setup_two_member_household
from tests.finance_helpers import category_id
from tests.forecast_helpers import create_recurring

pytestmark = pytest.mark.integration


def _today() -> date:
    return parse_period(current_period("Europe/Paris"))[0]


def _record_balance(client: TestClient) -> None:
    response = client.put(
        "/api/v1/users/me/personal-balance",
        json={
            "balance_cents": 100000,
            "recorded_at": (datetime.now(UTC) - timedelta(hours=1)).isoformat(),
        },
        headers={"X-CSRF-Token": get_csrf(client)},
    )
    assert response.status_code == 201, response.text


def test_dashboard_generates_missing_personal_occurrences(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    setup_two_member_household(client, db_session, test_settings)
    _record_balance(client)
    recurring = create_recurring(
        client,
        category_id=category_id(client, "Logement"),
        amount_cents=2000,
        start_date=_today(),
        due_day=1,
    ).json()

    response = client.get("/api/v1/users/me/dashboard")

    assert response.status_code == 200, response.text
    assert response.json()["deductions"]["personal_recurring_remaining_cents"] == 2000
    assert response.json()["upcoming_recurring"][0]["recurring_expense_id"] == recurring["id"]

    db_session.expire_all()
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(RecurringOccurrence)
            .where(RecurringOccurrence.recurring_expense_id == recurring["id"])
        )
        == 1
    )


def test_contributions_generate_missing_shared_occurrences(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    setup_two_member_household(client, db_session, test_settings)
    create_recurring(
        client,
        category_id=category_id(client, "Logement"),
        amount_cents=10000,
        scope="shared",
        start_date=_today(),
        due_day=1,
    )

    response = client.get("/api/v1/households/me/contributions")

    assert response.status_code == 200, response.text
    contributions = response.json()
    assert len(contributions) == 2
    assert sum(item["amount_cents"] for item in contributions) == 10000 + 49000


def test_generate_all_for_period_is_idempotent(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    setup_two_member_household(client, db_session, test_settings)
    recurring = create_recurring(
        client,
        category_id=category_id(client, "Transport"),
        amount_cents=3000,
        start_date=date(2025, 1, 15),
        due_day=15,
    ).json()

    first = RecurringService(db_session).generate_all_for_period("2025-01")
    second = RecurringService(db_session).generate_all_for_period("2025-01")

    assert first == 1
    assert second == 0
    db_session.expire_all()
    occurrences = list(
        db_session.scalars(
            select(RecurringOccurrence).where(
                RecurringOccurrence.recurring_expense_id == recurring["id"]
            )
        ).all()
    )
    assert len(occurrences) == 1
    assert occurrences[0].due_date == date(2025, 1, 15)


def test_inactive_recurring_is_not_generated(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    setup_two_member_household(client, db_session, test_settings)
    recurring = create_recurring(
        client,
        category_id=category_id(client, "Transport"),
        amount_cents=3000,
        start_date=date(2025, 1, 15),
        due_day=15,
    ).json()
    deactivate = client.post(
        f"/api/v1/recurring-expenses/{recurring['id']}/deactivate",
        headers={"X-CSRF-Token": get_csrf(client)},
    )
    assert deactivate.status_code == 200

    generated = RecurringService(db_session).generate_all_for_period("2025-01")

    assert generated == 0
