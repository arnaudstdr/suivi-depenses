from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.periods import current_period
from app.domains.audit.models import AuditLog
from app.domains.transactions.models import Transaction
from tests.auth_helpers import get_csrf, setup_two_member_household
from tests.finance_helpers import category_id
from tests.forecast_helpers import create_recurring

pytestmark = pytest.mark.integration


def _contributions(client: TestClient, period: str) -> list[dict]:
    response = client.get(
        "/api/v1/households/me/contributions",
        params={"period": period},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _for_user(rows: list[dict], user_id: str) -> dict:
    return next(row for row in rows if row["user_id"] == user_id)


def _set_default_rule(
    client: TestClient,
    *,
    owner_id: str,
    member_id: str,
    owner_percentage: str,
    member_percentage: str,
):
    return client.put(
        "/api/v1/households/me/allocation-rules/default",
        json={
            "members": [
                {"user_id": owner_id, "percentage": owner_percentage},
                {"user_id": member_id, "percentage": member_percentage},
            ]
        },
        headers={"X-CSRF-Token": get_csrf(client)},
    )


def test_past_contribution_is_not_rewritten_by_a_rule_change(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    owner_id, member_id = setup_two_member_household(client, db_session, test_settings)
    first = _contributions(client, "2025-01")
    owner_before = _for_user(first, owner_id)

    update = _set_default_rule(
        client,
        owner_id=owner_id,
        member_id=member_id,
        owner_percentage="60.000",
        member_percentage="40.000",
    )
    assert update.status_code == 200, update.text

    past_again = _contributions(client, "2025-01")
    owner_after = _for_user(past_again, owner_id)
    assert owner_after["amount_cents"] == owner_before["amount_cents"] == 26950
    assert Decimal(str(owner_after["allocation_percentage"])) == Decimal("55.000")

    current = _for_user(
        _contributions(client, current_period("Europe/Paris")),
        owner_id,
    )
    assert current["amount_cents"] == 29400
    assert Decimal(str(current["allocation_percentage"])) == Decimal("60.000")


def test_transferred_contribution_can_be_corrected_and_audited(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    owner_id, _ = setup_two_member_household(client, db_session, test_settings)
    contribution = _for_user(
        _contributions(client, current_period("Europe/Paris")),
        owner_id,
    )
    transferred_at = datetime.now(UTC) - timedelta(hours=2)
    transferred = client.post(
        f"/api/v1/households/me/contributions/{contribution['id']}/mark-transferred",
        json={
            "transferred_at": transferred_at.isoformat(),
            "transferred_amount_cents": contribution["amount_cents"],
        },
        headers={"X-CSRF-Token": get_csrf(client)},
    )
    assert transferred.status_code == 200, transferred.text

    corrected_at = datetime.now(UTC) - timedelta(hours=1)
    corrected = client.post(
        f"/api/v1/households/me/contributions/{contribution['id']}/correct-transfer",
        json={
            "transferred_at": corrected_at.isoformat(),
            "transferred_amount_cents": 25000,
            "note": "Virement corrigé",
        },
        headers={"X-CSRF-Token": get_csrf(client)},
    )

    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["transferred_amount_cents"] == 25000

    db_session.expire_all()
    stored = db_session.get(
        Transaction,
        corrected.json()["transaction_id"],
    )
    assert stored is not None
    assert stored.amount_cents == 25000
    assert stored.notes == "Virement corrigé"

    log = db_session.scalar(
        select(AuditLog).where(
            AuditLog.action == "household_contribution.payment_corrected",
        )
    )
    assert log is not None
    assert log.details is not None
    assert log.details["previous_amount_cents"] == contribution["amount_cents"]
    assert log.details["amount_cents"] == 25000


def test_only_owner_of_contribution_can_correct_it(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    owner_id, _ = setup_two_member_household(client, db_session, test_settings)
    contribution = _for_user(
        _contributions(client, current_period("Europe/Paris")),
        owner_id,
    )
    client.cookies.clear()
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": "member@example.com", "password": "another-strong-password"},
            headers={"X-CSRF-Token": get_csrf(client)},
        ).status_code
        == 200
    )

    response = client.post(
        f"/api/v1/households/me/contributions/{contribution['id']}/correct-transfer",
        json={
            "transferred_at": datetime.now(UTC).isoformat(),
            "transferred_amount_cents": 1000,
        },
        headers={"X-CSRF-Token": get_csrf(client)},
    )

    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"


def test_correction_requires_a_transferred_contribution(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    owner_id, _ = setup_two_member_household(client, db_session, test_settings)
    contribution = _for_user(
        _contributions(client, current_period("Europe/Paris")),
        owner_id,
    )

    response = client.post(
        f"/api/v1/households/me/contributions/{contribution['id']}/correct-transfer",
        json={
            "transferred_at": datetime.now(UTC).isoformat(),
            "transferred_amount_cents": 1000,
        },
        headers={"X-CSRF-Token": get_csrf(client)},
    )

    assert response.status_code == 409
    assert response.json()["code"] == "contribution_not_transferred"


def test_contributions_history_returns_stored_periods(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    owner_id, member_id = setup_two_member_household(client, db_session, test_settings)
    _contributions(client, "2025-01")
    _contributions(client, "2025-02")

    response = client.get(
        "/api/v1/households/me/contributions/history",
        params={"date_from": "2025-01", "date_to": "2025-02"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["total"] == 4
    assert {item["user_id"] for item in payload["items"]} == {owner_id, member_id}
    assert [item["period"] for item in payload["items"]] == [
        "2025-02",
        "2025-02",
        "2025-01",
        "2025-01",
    ]


def test_clearing_a_specific_rule_removes_the_orphan_rule(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    owner_id, member_id = setup_two_member_household(client, db_session, test_settings)
    recurring = create_recurring(
        client,
        category_id=category_id(client, "Logement"),
        amount_cents=10000,
        scope="shared",
        start_date=date.today().replace(day=1),
        due_day=1,
    ).json()
    created = client.put(
        f"/api/v1/recurring-expenses/{recurring['id']}/allocation-rule",
        json={
            "members": [
                {"user_id": owner_id, "percentage": "50.000"},
                {"user_id": member_id, "percentage": "50.000"},
            ]
        },
        headers={"X-CSRF-Token": get_csrf(client)},
    )
    assert created.status_code == 200, created.text
    rule_id = created.json()["id"]

    cleared = client.delete(
        f"/api/v1/recurring-expenses/{recurring['id']}/allocation-rule",
        headers={"X-CSRF-Token": get_csrf(client)},
    )

    assert cleared.status_code == 204
    rules = client.get("/api/v1/households/me/allocation-rules").json()
    assert rule_id not in {rule["id"] for rule in rules}
    assert len(rules) == 1
    assert rules[0]["is_default"] is True


def test_allocation_update_audit_contains_before_and_after(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    owner_id, member_id = setup_two_member_household(client, db_session, test_settings)
    update = _set_default_rule(
        client,
        owner_id=owner_id,
        member_id=member_id,
        owner_percentage="70.000",
        member_percentage="30.000",
    )
    assert update.status_code == 200, update.text

    db_session.expire_all()
    log = db_session.scalar(select(AuditLog).where(AuditLog.action == "allocation.default_updated"))
    assert log is not None
    assert log.details is not None
    assert Decimal(log.details["before"][owner_id]) == Decimal("55.000")
    assert Decimal(log.details["after"][owner_id]) == Decimal("70.000")
