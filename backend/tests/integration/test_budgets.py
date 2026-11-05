from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.domains.audit.models import AuditLog
from app.domains.budgets.models import Budget, BudgetPeriod
from tests.auth_helpers import (
    INVITEE_EMAIL,
    INVITEE_FIRST_NAME,
    INVITEE_PASSWORD,
    accept_invitation,
    bootstrap_owner,
    create_invitation,
    login,
)
from tests.finance_helpers import (
    create_transaction,
    grocery_budget,
    grocery_category_id,
    update_grocery_budget,
)

pytestmark = pytest.mark.integration


def test_grocery_budget_is_created_at_bootstrap(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)
    assert login(client).status_code == 200

    response = grocery_budget(client)

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "Budget courses"
    assert payload["default_amount_cents"] == 49000
    assert payload["allocated_cents"] == 49000
    assert payload["spent_cents"] == 0
    assert payload["remaining_cents"] == 49000

    db_session.expire_all()
    budgets = list(db_session.scalars(select(Budget)).all())
    assert len(budgets) == 1
    assert budgets[0].budget_type == "grocery"
    assert budgets[0].default_amount_cents == 49000
    assert db_session.scalar(select(BudgetPeriod)) is not None


def test_grocery_budget_can_be_updated_by_owner(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)
    assert login(client).status_code == 200

    response = update_grocery_budget(client, 60000)

    assert response.status_code == 200
    assert response.json()["default_amount_cents"] == 60000
    assert response.json()["allocated_cents"] == 60000
    assert grocery_budget(client).json()["remaining_cents"] == 60000

    db_session.expire_all()
    actions = set(db_session.scalars(select(AuditLog.action)).all())
    assert "budget.grocery_updated" in actions


def test_grocery_budget_update_requires_owner_and_csrf(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)
    assert login(client).status_code == 200

    no_csrf = client.patch(
        "/api/v1/households/me/grocery-budget",
        json={"default_amount_cents": 60000},
    )
    assert no_csrf.status_code == 403

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

    forbidden = update_grocery_budget(client, 60000)
    assert forbidden.status_code == 403
    assert forbidden.json()["code"] == "forbidden"


def test_no_budget_carryover_between_months(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)
    assert login(client).status_code == 200
    grocery_id = grocery_category_id(client)

    today = date.today()
    assert (
        create_transaction(
            client,
            category_id=grocery_id,
            amount_cents=10000,
            scope="shared",
            transaction_date=today,
        ).status_code
        == 201
    )

    next_month = (today.replace(day=1) + timedelta(days=32)).strftime("%Y-%m")
    response = grocery_budget(client, next_month)

    assert response.status_code == 200
    payload = response.json()
    assert payload["allocated_cents"] == 49000
    assert payload["spent_cents"] == 0
    assert payload["remaining_cents"] == 49000


def test_grocery_transactions_are_scoped_to_period(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)
    assert login(client).status_code == 200
    grocery_id = grocery_category_id(client)
    today = date.today()

    assert (
        create_transaction(
            client,
            category_id=grocery_id,
            amount_cents=2000,
            scope="shared",
            transaction_date=today,
        ).status_code
        == 201
    )
    assert (
        create_transaction(
            client,
            category_id=grocery_id,
            amount_cents=3000,
            scope="shared",
            transaction_date=today.replace(day=1) - timedelta(days=1),
        ).status_code
        == 201
    )

    listing = client.get(
        "/api/v1/households/me/grocery-budget/transactions",
        params={"period": today.strftime("%Y-%m")},
    )

    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["amount_cents"] == 2000


def test_invalid_period_is_rejected(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)
    assert login(client).status_code == 200

    response = grocery_budget(client, "2026-13")

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_period"


def test_grocery_budget_is_readable_by_member(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)
    assert login(client).status_code == 200
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

    response = grocery_budget(client)
    assert response.status_code == 200
    assert response.json()["allocated_cents"] == 49000

    # La lecture ne nécessite pas CSRF.
    assert client.get("/api/v1/households/me/grocery-budget").status_code == 200

    # Le point de contrôle CSRF global reste requis pour les mutations.
    assert (
        client.patch(
            "/api/v1/households/me/grocery-budget",
            json={"default_amount_cents": 50000},
        ).status_code
        == 403
    )
