from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import Settings
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
from tests.finance_helpers import category_id
from tests.forecast_helpers import create_recurring

pytestmark = pytest.mark.integration


def _two_member_household(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> tuple[str, str]:
    bootstrap_owner(db_session, test_settings)
    assert login(client).status_code == 200
    owner_id = client.get("/api/v1/auth/me").json()["user"]["id"]
    invitation = create_invitation(client, email=INVITEE_EMAIL)
    client.cookies.clear()
    accepted = accept_invitation(
        client,
        token=invitation.json()["token"],
        email=INVITEE_EMAIL,
        first_name=INVITEE_FIRST_NAME,
        password=INVITEE_PASSWORD,
    )
    assert accepted.status_code == 201
    member_id = accepted.json()["user"]["id"]
    client.cookies.clear()
    assert login(client).status_code == 200
    return owner_id, member_id


def _rules(client: TestClient) -> list[dict[str, object]]:
    response = client.get("/api/v1/households/me/allocation-rules")
    assert response.status_code == 200
    return list(response.json())


def test_default_rule_is_100_then_55_45(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)
    assert login(client).status_code == 200
    owner_id = client.get("/api/v1/auth/me").json()["user"]["id"]

    initial = _rules(client)
    assert len(initial) == 1
    assert initial[0]["is_default"] is True
    assert initial[0]["members"][0]["user_id"] == owner_id
    assert initial[0]["members"][0]["percentage"] in {"100", "100.000"}

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

    rules = _rules(client)
    assert len(rules) == 1
    percentages = sorted(Decimal(str(member["percentage"])) for member in rules[0]["members"])
    assert percentages == [Decimal("45.000"), Decimal("55.000")]


def test_default_rule_can_be_customized(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    owner_id, member_id = _two_member_household(client, db_session, test_settings)

    response = client.put(
        "/api/v1/households/me/allocation-rules/default",
        json={
            "members": [
                {"user_id": owner_id, "percentage": "60.000"},
                {"user_id": member_id, "percentage": "40.000"},
            ]
        },
        headers={"X-CSRF-Token": get_csrf(client)},
    )

    assert response.status_code == 200, response.text
    assert sorted(Decimal(str(member["percentage"])) for member in response.json()["members"]) == [
        Decimal("40.000"),
        Decimal("60.000"),
    ]

    invalid_total = client.put(
        "/api/v1/households/me/allocation-rules/default",
        json={
            "members": [
                {"user_id": owner_id, "percentage": "60.000"},
                {"user_id": member_id, "percentage": "39.000"},
            ]
        },
        headers={"X-CSRF-Token": get_csrf(client)},
    )
    assert invalid_total.status_code == 422
    assert invalid_total.json()["code"] == "invalid_allocation"

    unknown_user = client.put(
        "/api/v1/households/me/allocation-rules/default",
        json={
            "members": [
                {"user_id": "00000000-0000-4000-8000-000000000099", "percentage": "100.000"},
            ]
        },
        headers={"X-CSRF-Token": get_csrf(client)},
    )
    assert unknown_user.status_code == 422


def test_member_cannot_change_default_rule(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    owner_id, member_id = _two_member_household(client, db_session, test_settings)

    client.cookies.clear()
    assert login(client, email=INVITEE_EMAIL, password=INVITEE_PASSWORD).status_code == 200

    response = client.put(
        "/api/v1/households/me/allocation-rules/default",
        json={
            "members": [
                {"user_id": owner_id, "percentage": "50.000"},
                {"user_id": member_id, "percentage": "50.000"},
            ]
        },
        headers={"X-CSRF-Token": get_csrf(client)},
    )

    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"


def test_recurring_specific_rule(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    owner_id, member_id = _two_member_household(client, db_session, test_settings)
    recurring = create_recurring(
        client,
        category_id=category_id(client, "Logement"),
        amount_cents=10000,
        scope="shared",
        start_date=date.today().replace(day=1),
        due_day=1,
    ).json()

    response = client.put(
        f"/api/v1/recurring-expenses/{recurring['id']}/allocation-rule",
        json={
            "members": [
                {"user_id": owner_id, "percentage": "70.000"},
                {"user_id": member_id, "percentage": "30.000"},
            ]
        },
        headers={"X-CSRF-Token": get_csrf(client)},
    )

    assert response.status_code == 200, response.text
    rule = response.json()
    assert rule["is_default"] is False
    assert sorted(Decimal(str(member["percentage"])) for member in rule["members"]) == [
        Decimal("30.000"),
        Decimal("70.000"),
    ]

    refreshed = client.get(f"/api/v1/recurring-expenses/{recurring['id']}")
    assert refreshed.json()["allocation_rule_id"] == rule["id"]

    cleared = client.delete(
        f"/api/v1/recurring-expenses/{recurring['id']}/allocation-rule",
        headers={"X-CSRF-Token": get_csrf(client)},
    )
    assert cleared.status_code == 204
    assert (
        client.get(f"/api/v1/recurring-expenses/{recurring['id']}").json()["allocation_rule_id"]
        is None
    )


def test_specific_rule_is_limited_to_shared_recurring(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    owner_id, member_id = _two_member_household(client, db_session, test_settings)
    personal = create_recurring(
        client,
        category_id=category_id(client, "Santé"),
        scope="personal",
    ).json()

    response = client.put(
        f"/api/v1/recurring-expenses/{personal['id']}/allocation-rule",
        json={
            "members": [
                {"user_id": owner_id, "percentage": "50.000"},
                {"user_id": member_id, "percentage": "50.000"},
            ]
        },
        headers={"X-CSRF-Token": get_csrf(client)},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "allocation_not_applicable"


def test_allocation_mutation_requires_csrf(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    owner_id, member_id = _two_member_household(client, db_session, test_settings)

    response = client.put(
        "/api/v1/households/me/allocation-rules/default",
        json={
            "members": [
                {"user_id": owner_id, "percentage": "50.000"},
                {"user_id": member_id, "percentage": "50.000"},
            ]
        },
    )

    assert response.status_code == 403
    assert response.json()["code"] == "csrf_failed"
