from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.domains.allocations.models import HouseholdContribution
from tests.auth_helpers import (
    INVITEE_PASSWORD,
    get_csrf,
    login,
    setup_two_member_household,
)
from tests.finance_helpers import category_id, create_transaction
from tests.forecast_helpers import create_planned, create_recurring, list_occurrences

pytestmark = pytest.mark.integration


def _contributions(client: TestClient, period: str | None = None) -> list[dict]:
    params = {"period": period} if period else {}
    response = client.get("/api/v1/households/me/contributions", params=params)
    assert response.status_code == 200, response.text
    return list(response.json())


def _for_user(items: list[dict], user_id: str) -> dict:
    return next(item for item in items if item["user_id"] == user_id)


def _mark_transferred(
    client: TestClient,
    contribution_id: str,
    *,
    amount_cents: int,
    transferred_at: str | None = None,
) -> dict:
    response = client.post(
        f"/api/v1/households/me/contributions/{contribution_id}/mark-transferred",
        json={
            "transferred_at": transferred_at or datetime.now(UTC).isoformat(),
            "transferred_amount_cents": amount_cents,
        },
        headers={"X-CSRF-Token": get_csrf(client)},
    )
    assert response.status_code == 200, response.text
    return dict(response.json())


def test_contribution_includes_grocery_budget(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    owner_id, member_id = setup_two_member_household(
        client,
        db_session,
        test_settings,
    )

    rows = _contributions(client)

    owner = _for_user(rows, owner_id)
    member = _for_user(rows, member_id)
    assert owner["amount_cents"] == 26950
    assert member["amount_cents"] == 22050
    assert Decimal(str(owner["allocation_percentage"])) == Decimal("55.000")
    assert Decimal(str(member["allocation_percentage"])) == Decimal("45.000")
    assert owner["status"] == "pending"
    assert owner["period"] == date.today().strftime("%Y-%m")

    again = _contributions(client)
    assert len(again) == 2


def test_contribution_aggregates_recurring_planned_and_transactions(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    owner_id, member_id = setup_two_member_household(
        client,
        db_session,
        test_settings,
    )
    today = date.today()
    period = today.strftime("%Y-%m")

    recurring = create_recurring(
        client,
        category_id=category_id(client, "Logement"),
        amount_cents=10000,
        scope="shared",
        start_date=today.replace(day=1),
        due_day=1,
    ).json()
    assert list_occurrences(client, recurring["id"], period=period).status_code == 200

    assert (
        create_planned(
            client,
            category_id=category_id(client, "Logement"),
            amount_cents=3000,
            scope="shared",
            planned_date=today,
            status="committed",
        ).status_code
        == 201
    )
    transaction = create_transaction(
        client,
        category_id=category_id(client, "Logement"),
        amount_cents=2001,
        scope="shared",
        transaction_date=today,
    )
    assert transaction.status_code == 201

    rows = _contributions(client)
    owner = _for_user(rows, owner_id)
    member = _for_user(rows, member_id)

    # 26950 + 5500 + 1650 + 1101 = 35201
    # 22050 + 4500 + 1350 + 900  = 28800
    assert owner["amount_cents"] == 35201
    assert member["amount_cents"] == 28800
    assert owner["amount_cents"] + member["amount_cents"] == 64001


def test_contribution_uses_specific_recurring_rule(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    owner_id, member_id = setup_two_member_household(
        client,
        db_session,
        test_settings,
    )
    today = date.today()
    recurring = create_recurring(
        client,
        category_id=category_id(client, "Logement"),
        amount_cents=10000,
        scope="shared",
        start_date=today.replace(day=1),
        due_day=1,
    ).json()
    rule = client.put(
        f"/api/v1/recurring-expenses/{recurring['id']}/allocation-rule",
        json={
            "members": [
                {"user_id": owner_id, "percentage": "70.000"},
                {"user_id": member_id, "percentage": "30.000"},
            ]
        },
        headers={"X-CSRF-Token": get_csrf(client)},
    )
    assert rule.status_code == 200
    assert (
        list_occurrences(
            client,
            recurring["id"],
            period=today.strftime("%Y-%m"),
        ).status_code
        == 200
    )

    rows = _contributions(client)

    assert _for_user(rows, owner_id)["amount_cents"] == 26950 + 7000
    assert _for_user(rows, member_id)["amount_cents"] == 22050 + 3000


def test_shared_refund_reduces_contribution(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    owner_id, member_id = setup_two_member_household(
        client,
        db_session,
        test_settings,
    )
    original = create_transaction(
        client,
        category_id=category_id(client, "Logement"),
        amount_cents=1000,
        scope="shared",
    ).json()
    refund = create_transaction(
        client,
        category_id=category_id(client, "Logement"),
        amount_cents=400,
        scope="shared",
        transaction_type="refund",
        original_transaction_id=original["id"],
    )
    assert refund.status_code == 201

    rows = _contributions(client)

    # Contributions courses : 26950 / 22050 ; net partagé 600 : 330 / 270.
    assert _for_user(rows, owner_id)["amount_cents"] == 26950 + 330
    assert _for_user(rows, member_id)["amount_cents"] == 22050 + 270


def test_transfer_is_idempotent_and_freezes_amount(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    owner_id, member_id = setup_two_member_household(
        client,
        db_session,
        test_settings,
    )
    rows = _contributions(client)
    owner = _for_user(rows, owner_id)

    transferred = _mark_transferred(
        client,
        owner["id"],
        amount_cents=owner["amount_cents"],
    )
    assert transferred["status"] == "transferred"
    assert transferred["transaction_id"] is not None

    again = _mark_transferred(
        client,
        owner["id"],
        amount_cents=owner["amount_cents"],
    )
    assert again["transaction_id"] == transferred["transaction_id"]

    # Une nouvelle charge ne modifie plus la contribution déjà transférée.
    create_transaction(
        client,
        category_id=category_id(client, "Logement"),
        amount_cents=1000,
        scope="shared",
    )
    refreshed = _contributions(client)
    assert _for_user(refreshed, owner_id)["amount_cents"] == owner["amount_cents"]
    assert _for_user(refreshed, member_id)["amount_cents"] == 22050 + 450

    db_session.expire_all()
    stored = db_session.get(HouseholdContribution, owner["id"])
    assert stored is not None
    assert stored.status == "transferred"
    assert stored.transaction_id is not None

    transaction = client.get(f"/api/v1/transactions/{stored.transaction_id}").json()
    assert transaction["scope"] == "personal"
    assert transaction["category_id"] == "00000000-0000-4000-8000-000000000009"
    assert transaction["amount_cents"] == owner["amount_cents"]


def test_member_can_only_mark_own_contribution(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    _owner_id, member_id = setup_two_member_household(
        client,
        db_session,
        test_settings,
    )
    rows = _contributions(client)
    member = _for_user(rows, member_id)

    forbidden = client.post(
        f"/api/v1/households/me/contributions/{member['id']}/mark-transferred",
        json={
            "transferred_at": datetime.now(UTC).isoformat(),
            "transferred_amount_cents": member["amount_cents"],
        },
        headers={"X-CSRF-Token": get_csrf(client)},
    )
    assert forbidden.status_code == 403

    client.cookies.clear()
    assert login(client, email="member@example.com", password=INVITEE_PASSWORD).status_code == 200
    allowed = _mark_transferred(
        client,
        member["id"],
        amount_cents=member["amount_cents"],
    )
    assert allowed["status"] == "transferred"


def test_transfer_requires_csrf(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    owner_id, _ = setup_two_member_household(client, db_session, test_settings)
    owner = _for_user(_contributions(client), owner_id)

    response = client.post(
        f"/api/v1/households/me/contributions/{owner['id']}/mark-transferred",
        json={
            "transferred_at": datetime.now(UTC).isoformat(),
            "transferred_amount_cents": owner["amount_cents"],
        },
    )

    assert response.status_code == 403
    assert response.json()["code"] == "csrf_failed"
