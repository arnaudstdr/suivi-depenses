from datetime import date
from typing import Any

from fastapi.testclient import TestClient
from httpx import Response

from tests.auth_helpers import get_csrf


def list_categories(client: TestClient) -> list[dict[str, Any]]:
    response = client.get("/api/v1/categories")
    assert response.status_code == 200
    return list(response.json())


def category_id(client: TestClient, name: str) -> str:
    for category in list_categories(client):
        if category["name"] == name:
            return str(category["id"])
    raise AssertionError(f"Catégorie absente : {name}")


def grocery_category_id(client: TestClient) -> str:
    for category in list_categories(client):
        if category["is_grocery"]:
            return str(category["id"])
    raise AssertionError("Catégorie courses absente")


def create_transaction(
    client: TestClient,
    *,
    category_id: str,
    label: str = "Dépense test",
    amount_cents: int = 1000,
    transaction_date: date = date.today(),
    scope: str = "personal",
    transaction_type: str = "expense",
    **extra: Any,
) -> Response:
    payload: dict[str, Any] = {
        "label": label,
        "amount_cents": amount_cents,
        "transaction_date": transaction_date.isoformat(),
        "category_id": category_id,
        "scope": scope,
        "transaction_type": transaction_type,
    }
    payload.update(extra)
    return client.post(
        "/api/v1/transactions",
        json=payload,
        headers={"X-CSRF-Token": get_csrf(client)},
    )


def create_category(
    client: TestClient,
    *,
    name: str,
    is_grocery: bool = False,
    icon: str | None = None,
) -> Response:
    return client.post(
        "/api/v1/categories",
        json={"name": name, "is_grocery": is_grocery, "icon": icon},
        headers={"X-CSRF-Token": get_csrf(client)},
    )


def grocery_budget(client: TestClient, period: str | None = None) -> Response:
    params = {"period": period} if period else {}
    return client.get("/api/v1/households/me/grocery-budget", params=params)


def update_grocery_budget(client: TestClient, amount_cents: int) -> Response:
    return client.patch(
        "/api/v1/households/me/grocery-budget",
        json={"default_amount_cents": amount_cents},
        headers={"X-CSRF-Token": get_csrf(client)},
    )
