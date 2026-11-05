from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import Settings
from tests.auth_helpers import (
    bootstrap_owner,
    get_csrf,
    login,
    setup_two_member_household,
)
from tests.finance_helpers import category_id, create_transaction
from tests.forecast_helpers import (
    create_planned,
    create_recurring,
    list_occurrences,
    mark_occurrence_paid,
    mark_planned_paid,
)

pytestmark = pytest.mark.integration


def _period() -> str:
    return date.today().strftime("%Y-%m")


def _record_balance(
    client: TestClient,
    *,
    balance_cents: int,
    recorded_at: datetime,
) -> None:
    response = client.put(
        "/api/v1/users/me/personal-balance",
        json={
            "balance_cents": balance_cents,
            "recorded_at": recorded_at.isoformat(),
        },
        headers={"X-CSRF-Token": get_csrf(client)},
    )
    assert response.status_code == 201, response.text


def _dashboard(client: TestClient, period: str | None = None):
    params = {"period": period} if period else {}
    response = client.get("/api/v1/users/me/dashboard", params=params)
    return response


def _snapshot() -> datetime:
    return datetime.now(UTC) - timedelta(hours=1)


def test_dashboard_requires_auth_and_balance(client: TestClient) -> None:
    assert _dashboard(client).status_code == 401


def test_dashboard_requires_a_personal_balance(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)
    assert login(client).status_code == 200

    response = _dashboard(client)

    assert response.status_code == 409
    assert response.json()["code"] == "balance_required"


def test_dashboard_excludes_transactions_already_in_snapshot(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    setup_two_member_household(client, db_session, test_settings)
    snapshot = _snapshot()
    _record_balance(client, balance_cents=100000, recorded_at=snapshot)
    transport = category_id(client, "Transport")

    before = create_transaction(
        client,
        category_id=transport,
        amount_cents=5000,
        paid_at=(snapshot - timedelta(minutes=30)).isoformat(),
    )
    after = create_transaction(
        client,
        category_id=transport,
        amount_cents=3000,
        paid_at=(snapshot + timedelta(minutes=30)).isoformat(),
    )
    assert before.status_code == 201
    assert after.status_code == 201

    response = _dashboard(client)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["deductions"]["personal_transactions_remaining_cents"] == 3000
    assert payload["deductions"]["household_contribution_remaining_cents"] == 26950
    assert payload["available_forecast_cents"] == 100000 - 3000 - 26950
    assert payload["deductions"]["household_contribution_status"] == "pending"
    assert payload["grocery_budget"]["allocated_cents"] == 49000


def test_dashboard_nets_personal_refund_after_snapshot(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    setup_two_member_household(client, db_session, test_settings)
    snapshot = _snapshot()
    _record_balance(client, balance_cents=100000, recorded_at=snapshot)
    transport = category_id(client, "Transport")

    original = create_transaction(
        client,
        category_id=transport,
        amount_cents=1000,
        paid_at=(snapshot - timedelta(minutes=30)).isoformat(),
    ).json()
    refund = create_transaction(
        client,
        category_id=transport,
        amount_cents=400,
        transaction_type="refund",
        original_transaction_id=original["id"],
        paid_at=(snapshot + timedelta(minutes=30)).isoformat(),
    )
    assert refund.status_code == 201

    dashboard = _dashboard(client).json()

    assert dashboard["deductions"]["personal_transactions_remaining_cents"] == -400
    assert dashboard["available_forecast_cents"] == 100000 + 400 - 26950


def test_dashboard_handles_recurring_snapshot_boundary(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    setup_two_member_household(client, db_session, test_settings)
    snapshot = _snapshot()
    _record_balance(client, balance_cents=100000, recorded_at=snapshot)
    today = date.today()

    pending = create_recurring(
        client,
        category_id=category_id(client, "Logement"),
        amount_cents=2000,
        start_date=today.replace(day=1),
        due_day=1,
    ).json()
    paid_after = create_recurring(
        client,
        category_id=category_id(client, "Transport"),
        amount_cents=1500,
        start_date=today.replace(day=1),
        due_day=1,
    ).json()
    paid_before = create_recurring(
        client,
        category_id=category_id(client, "Santé"),
        amount_cents=900,
        start_date=today.replace(day=1),
        due_day=1,
    ).json()

    pending_occurrence = list_occurrences(
        client,
        pending["id"],
        period=_period(),
    ).json()[0]
    after_occurrence = list_occurrences(
        client,
        paid_after["id"],
        period=_period(),
    ).json()[0]
    before_occurrence = list_occurrences(
        client,
        paid_before["id"],
        period=_period(),
    ).json()[0]

    assert pending_occurrence["status"] == "pending"
    assert (
        mark_occurrence_paid(
            client,
            after_occurrence["id"],
            paid_at=(snapshot + timedelta(minutes=10)).isoformat(),
        ).status_code
        == 200
    )
    assert (
        mark_occurrence_paid(
            client,
            before_occurrence["id"],
            paid_at=(snapshot - timedelta(minutes=10)).isoformat(),
        ).status_code
        == 200
    )

    response = _dashboard(client)

    assert response.status_code == 200
    assert response.json()["deductions"]["personal_recurring_remaining_cents"] == 3500
    assert len(response.json()["upcoming_recurring"]) == 1
    assert response.json()["upcoming_recurring"][0]["amount_cents"] == 2000
    assert response.json()["available_forecast_cents"] == 100000 - 3500 - 26950


def test_dashboard_handles_planned_snapshot_boundary(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    setup_two_member_household(client, db_session, test_settings)
    snapshot = _snapshot()
    _record_balance(client, balance_cents=100000, recorded_at=snapshot)
    today = date.today()
    category = category_id(client, "Loisirs")

    committed = create_planned(
        client,
        category_id=category,
        amount_cents=1200,
        planned_date=today,
        status="committed",
    ).json()
    paid_after = create_planned(
        client,
        category_id=category,
        amount_cents=800,
        planned_date=today,
    ).json()
    paid_before = create_planned(
        client,
        category_id=category,
        amount_cents=700,
        planned_date=today,
    ).json()
    cancelled = create_planned(
        client,
        category_id=category,
        amount_cents=600,
        planned_date=today,
    ).json()

    assert (
        mark_planned_paid(
            client,
            paid_after["id"],
            paid_at=(snapshot + timedelta(minutes=10)).isoformat(),
        ).status_code
        == 200
    )
    assert (
        mark_planned_paid(
            client,
            paid_before["id"],
            paid_at=(snapshot - timedelta(minutes=10)).isoformat(),
        ).status_code
        == 200
    )
    assert (
        client.delete(
            f"/api/v1/planned-expenses/{cancelled['id']}",
            headers={"X-CSRF-Token": get_csrf(client)},
        ).status_code
        == 204
    )

    response = _dashboard(client)

    assert response.status_code == 200
    assert response.json()["deductions"]["personal_planned_remaining_cents"] == 2000
    assert response.json()["available_forecast_cents"] == 100000 - 2000 - 26950
    assert committed["id"]  # la dépense engagée reste déduite


def test_dashboard_handles_contribution_transfer_without_double_count(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    owner_id, _ = setup_two_member_household(client, db_session, test_settings)
    snapshot = _snapshot()
    _record_balance(client, balance_cents=100000, recorded_at=snapshot)

    initial = _dashboard(client).json()
    owner_contribution = next(
        contribution
        for contribution in client.get("/api/v1/households/me/contributions").json()
        if contribution["user_id"] == owner_id
    )
    transferred_at = snapshot + timedelta(minutes=10)
    transferred = client.post(
        f"/api/v1/households/me/contributions/{owner_contribution['id']}/mark-transferred",
        json={
            "transferred_at": transferred_at.isoformat(),
            "transferred_amount_cents": initial["deductions"][
                "household_contribution_remaining_cents"
            ],
        },
        headers={"X-CSRF-Token": get_csrf(client)},
    )
    assert transferred.status_code == 200

    response = _dashboard(client)

    assert response.status_code == 200
    assert response.json()["deductions"]["household_contribution_remaining_cents"] == 26950
    assert response.json()["deductions"]["household_contribution_status"] == "transferred"
    # La transaction de contribution ne doit pas être ajoutée aux transactions
    # personnelles déduites.
    assert response.json()["deductions"]["personal_transactions_remaining_cents"] == 0
    assert response.json()["available_forecast_cents"] == 100000 - 26950

    later_snapshot = datetime.now(UTC) + timedelta(minutes=30)
    _record_balance(client, balance_cents=90000, recorded_at=later_snapshot)
    after = _dashboard(client)
    assert after.json()["deductions"]["household_contribution_remaining_cents"] == 0
    assert after.json()["available_forecast_cents"] == 90000


def test_dashboard_excludes_offset_grocery_purchases(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    setup_two_member_household(client, db_session, test_settings)
    snapshot = _snapshot()
    _record_balance(client, balance_cents=100000, recorded_at=snapshot)
    grocery_id = next(
        category["id"]
        for category in client.get("/api/v1/categories").json()
        if category["is_grocery"]
    )

    response = create_transaction(
        client,
        category_id=grocery_id,
        amount_cents=10000,
        scope="shared",
        paid_at=(snapshot + timedelta(minutes=10)).isoformat(),
    )
    assert response.status_code == 201

    dashboard = _dashboard(client).json()

    assert dashboard["deductions"]["personal_transactions_remaining_cents"] == 0
    assert dashboard["available_forecast_cents"] == 100000 - 26950
    assert dashboard["grocery_budget"]["spent_cents"] == 10000
    assert dashboard["grocery_budget"]["remaining_cents"] == 39000


def test_dashboard_resets_after_new_balance_snapshot(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    setup_two_member_household(client, db_session, test_settings)
    first_snapshot = _snapshot() - timedelta(hours=1)
    _record_balance(client, balance_cents=100000, recorded_at=first_snapshot)

    transaction = create_transaction(
        client,
        category_id=category_id(client, "Transport"),
        amount_cents=5000,
        paid_at=(first_snapshot + timedelta(minutes=10)).isoformat(),
    )
    assert transaction.status_code == 201
    assert _dashboard(client).json()["deductions"]["personal_transactions_remaining_cents"] == 5000

    _record_balance(
        client,
        balance_cents=95000,
        recorded_at=datetime.now(UTC) + timedelta(minutes=30),
    )
    dashboard = _dashboard(client).json()

    assert dashboard["deductions"]["personal_transactions_remaining_cents"] == 0
    assert dashboard["available_forecast_cents"] == 95000 - 26950


def test_dashboard_lists_upcoming_and_recent_items(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    setup_two_member_household(client, db_session, test_settings)
    snapshot = _snapshot()
    _record_balance(client, balance_cents=100000, recorded_at=snapshot)
    today = date.today()
    recurring = create_recurring(
        client,
        category_id=category_id(client, "Logement"),
        label="Loyer",
        amount_cents=80000,
        start_date=today.replace(day=1),
        due_day=1,
    ).json()
    list_occurrences(client, recurring["id"], period=_period())
    create_transaction(
        client,
        category_id=category_id(client, "Transport"),
        label="Essence",
        amount_cents=3000,
        paid_at=(snapshot + timedelta(minutes=10)).isoformat(),
    )

    dashboard = _dashboard(client).json()

    assert dashboard["upcoming_recurring"][0]["label"] == "Loyer"
    assert dashboard["recent_personal_transactions"][0]["label"] == "Essence"


def test_dashboard_rejects_non_current_period(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    setup_two_member_household(client, db_session, test_settings)
    _record_balance(client, balance_cents=100000, recorded_at=_snapshot())

    response = _dashboard(client, "2020-01")

    assert response.status_code == 422
    assert response.json()["code"] == "unsupported_period"
