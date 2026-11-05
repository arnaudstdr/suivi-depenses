from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.domains.audit.models import AuditLog
from app.domains.transactions.models import Transaction
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
    create_category,
    create_transaction,
    grocery_budget,
    grocery_category_id,
)

pytestmark = pytest.mark.integration


def test_personal_transaction_is_created_and_listed(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)
    assert login(client).status_code == 200
    transport_id = category_id(client, "Transport")

    response = create_transaction(
        client,
        category_id=transport_id,
        label="Plein de carburant",
        amount_cents=6543,
        scope="personal",
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["scope"] == "personal"
    assert payload["household_id"] is None
    assert payload["budget_id"] is None
    assert payload["status"] == "paid"
    assert payload["paid_at"] is not None
    assert payload["amount_cents"] == 6543

    listing = client.get("/api/v1/transactions")
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["id"] == payload["id"]

    detail = client.get(f"/api/v1/transactions/{payload['id']}")
    assert detail.status_code == 200
    assert detail.json()["label"] == "Plein de carburant"


def test_shared_grocery_transaction_consumes_budget(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)
    assert login(client).status_code == 200
    grocery_id = grocery_category_id(client)

    response = create_transaction(
        client,
        category_id=grocery_id,
        label="Courses",
        amount_cents=6840,
        scope="shared",
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["household_id"] is not None
    assert payload["budget_id"] is not None

    budget = grocery_budget(client)
    assert budget.status_code == 200
    assert budget.json()["allocated_cents"] == 49000
    assert budget.json()["spent_cents"] == 6840
    assert budget.json()["remaining_cents"] == 42160

    grocery_transactions = client.get("/api/v1/households/me/grocery-budget/transactions")
    assert grocery_transactions.status_code == 200
    assert grocery_transactions.json()["total"] == 1


def test_shared_non_grocery_transaction_has_no_budget(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)
    assert login(client).status_code == 200

    response = create_transaction(
        client,
        category_id=category_id(client, "Logement"),
        label="Loyer",
        amount_cents=80000,
        scope="shared",
    )

    assert response.status_code == 201
    assert response.json()["budget_id"] is None
    assert response.json()["household_id"] is not None


def test_budget_is_rejected_for_personal_or_non_grocery_transactions(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)
    assert login(client).status_code == 200
    budget = grocery_budget(client).json()
    grocery_id = grocery_category_id(client)

    personal_with_budget = create_transaction(
        client,
        category_id=category_id(client, "Transport"),
        scope="personal",
        budget_id=budget["budget_id"],
    )
    assert personal_with_budget.status_code == 422
    assert personal_with_budget.json()["code"] == "invalid_budget"

    shared_non_grocery_with_budget = create_transaction(
        client,
        category_id=category_id(client, "Logement"),
        scope="shared",
        budget_id=budget["budget_id"],
    )
    assert shared_non_grocery_with_budget.status_code == 422

    wrong_budget = create_transaction(
        client,
        category_id=grocery_id,
        scope="shared",
        budget_id="00000000-0000-4000-8000-000000000099",
    )
    assert wrong_budget.status_code == 422


def test_refund_rules(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)
    assert login(client).status_code == 200
    transport_id = category_id(client, "Transport")
    original = create_transaction(
        client,
        category_id=transport_id,
        amount_cents=10000,
        scope="personal",
    ).json()

    refund = create_transaction(
        client,
        category_id=transport_id,
        amount_cents=4000,
        scope="personal",
        transaction_type="refund",
        original_transaction_id=original["id"],
        label="Remboursement partiel",
    )
    assert refund.status_code == 201, refund.text

    too_much = create_transaction(
        client,
        category_id=transport_id,
        amount_cents=7000,
        scope="personal",
        transaction_type="refund",
        original_transaction_id=original["id"],
    )
    assert too_much.status_code == 422
    assert too_much.json()["code"] == "invalid_refund"

    delete_original = client.delete(
        f"/api/v1/transactions/{original['id']}",
        headers={"X-CSRF-Token": get_csrf(client)},
    )
    assert delete_original.status_code == 409
    assert delete_original.json()["code"] == "transaction_has_refunds"

    lower_original = client.patch(
        f"/api/v1/transactions/{original['id']}",
        json={"amount_cents": 3000},
        headers={"X-CSRF-Token": get_csrf(client)},
    )
    assert lower_original.status_code == 422

    delete_refund = client.delete(
        f"/api/v1/transactions/{refund.json()['id']}",
        headers={"X-CSRF-Token": get_csrf(client)},
    )
    assert delete_refund.status_code == 204

    replacement = create_transaction(
        client,
        category_id=transport_id,
        amount_cents=6000,
        scope="personal",
        transaction_type="refund",
        original_transaction_id=original["id"],
    )
    assert replacement.status_code == 201


def test_refund_can_reuse_an_inactive_category(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)
    assert login(client).status_code == 200
    category = create_category(client, name="Animaux").json()
    original = create_transaction(
        client,
        category_id=category["id"],
        amount_cents=3000,
    ).json()

    deactivated = client.patch(
        f"/api/v1/categories/{category['id']}",
        json={"is_active": False},
        headers={"X-CSRF-Token": get_csrf(client)},
    )
    assert deactivated.status_code == 200

    refund = create_transaction(
        client,
        category_id=category["id"],
        amount_cents=1000,
        transaction_type="refund",
        original_transaction_id=original["id"],
    )

    assert refund.status_code == 201, refund.text


def test_grocery_refund_reduces_budget_spending(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)
    assert login(client).status_code == 200
    grocery_id = grocery_category_id(client)
    original = create_transaction(
        client,
        category_id=grocery_id,
        amount_cents=5000,
        scope="shared",
    ).json()

    refund = create_transaction(
        client,
        category_id=grocery_id,
        amount_cents=2000,
        scope="shared",
        transaction_type="refund",
        original_transaction_id=original["id"],
    )
    assert refund.status_code == 201, refund.text

    budget = grocery_budget(client).json()
    assert budget["spent_cents"] == 3000
    assert budget["remaining_cents"] == 46000


def test_transaction_is_soft_deleted(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)
    assert login(client).status_code == 200
    created = create_transaction(
        client,
        category_id=category_id(client, "Transport"),
        amount_cents=1000,
    ).json()

    response = client.delete(
        f"/api/v1/transactions/{created['id']}",
        headers={"X-CSRF-Token": get_csrf(client)},
    )

    assert response.status_code == 204
    assert client.get(f"/api/v1/transactions/{created['id']}").status_code == 404
    assert client.get("/api/v1/transactions").json()["total"] == 0

    db_session.expire_all()
    stored = db_session.get(Transaction, created["id"])
    assert stored is not None
    assert stored.deleted_at is not None


def test_personal_transaction_is_hidden_from_other_member(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)
    assert login(client).status_code == 200
    personal = create_transaction(
        client,
        category_id=category_id(client, "Transport"),
        amount_cents=1200,
        scope="personal",
    ).json()
    shared = create_transaction(
        client,
        category_id=category_id(client, "Logement"),
        amount_cents=80000,
        scope="shared",
    ).json()
    invitation = create_invitation(client, email=INVITEE_EMAIL)
    assert invitation.status_code == 201

    client.cookies.clear()
    accepted = accept_invitation(
        client,
        token=invitation.json()["token"],
        email=INVITEE_EMAIL,
        first_name=INVITEE_FIRST_NAME,
        password=INVITEE_PASSWORD,
    )
    assert accepted.status_code == 201

    assert client.get(f"/api/v1/transactions/{personal['id']}").status_code == 404
    assert client.get(f"/api/v1/transactions/{shared['id']}").status_code == 200

    listing = client.get("/api/v1/transactions").json()
    ids = {item["id"] for item in listing["items"]}
    assert personal["id"] not in ids
    assert shared["id"] in ids


def test_transaction_filters_and_pagination(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)
    assert login(client).status_code == 200
    transport_id = category_id(client, "Transport")
    today = date.today()

    for index in range(3):
        response = create_transaction(
            client,
            category_id=transport_id,
            label=f"Carburant {index}",
            amount_cents=1000 + index,
            transaction_date=today - timedelta(days=index),
        )
        assert response.status_code == 201

    filtered = client.get(
        "/api/v1/transactions",
        params={"search": "Carburant", "limit": 2, "offset": 0},
    )
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 3
    assert len(filtered.json()["items"]) == 2

    by_date = client.get(
        "/api/v1/transactions",
        params={
            "date_from": (today - timedelta(days=1)).isoformat(),
            "date_to": today.isoformat(),
        },
    )
    assert by_date.status_code == 200
    assert by_date.json()["total"] == 2


def test_transaction_mutation_requires_csrf(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)
    assert login(client).status_code == 200

    response = client.post(
        "/api/v1/transactions",
        json={
            "label": "Sans CSRF",
            "amount_cents": 1000,
            "transaction_date": date.today().isoformat(),
            "category_id": category_id(client, "Transport"),
            "scope": "personal",
        },
    )

    assert response.status_code == 403
    assert response.json()["code"] == "csrf_failed"


def test_transaction_update_is_audited(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    bootstrap_owner(db_session, test_settings)
    assert login(client).status_code == 200
    created = create_transaction(
        client,
        category_id=category_id(client, "Transport"),
        amount_cents=1000,
    ).json()

    response = client.patch(
        f"/api/v1/transactions/{created['id']}",
        json={"label": "Libellé corrigé", "amount_cents": 2000},
        headers={"X-CSRF-Token": get_csrf(client)},
    )

    assert response.status_code == 200
    assert response.json()["label"] == "Libellé corrigé"
    assert response.json()["amount_cents"] == 2000

    db_session.expire_all()
    actions = set(db_session.scalars(select(AuditLog.action)).all())
    assert {"transaction.created", "transaction.updated"} <= actions
