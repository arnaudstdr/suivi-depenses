from datetime import date
from typing import Any

from fastapi.testclient import TestClient
from httpx import Response

from tests.auth_helpers import get_csrf


def create_planned(
    client: TestClient,
    *,
    category_id: str,
    label: str = "Dépense prévue",
    amount_cents: int = 5000,
    planned_date: date = date.today(),
    scope: str = "personal",
    **extra: Any,
) -> Response:
    payload: dict[str, Any] = {
        "label": label,
        "amount_cents": amount_cents,
        "planned_date": planned_date.isoformat(),
        "category_id": category_id,
        "scope": scope,
    }
    payload.update(extra)
    return client.post(
        "/api/v1/planned-expenses",
        json=payload,
        headers={"X-CSRF-Token": get_csrf(client)},
    )


def mark_planned_paid(
    client: TestClient,
    planned_id: str,
    *,
    paid_at: str = "2026-11-05T10:00:00+01:00",
    payment_amount_cents: int | None = None,
    note: str | None = None,
) -> Response:
    payload: dict[str, Any] = {"paid_at": paid_at}
    if payment_amount_cents is not None:
        payload["payment_amount_cents"] = payment_amount_cents
    if note is not None:
        payload["note"] = note
    return client.post(
        f"/api/v1/planned-expenses/{planned_id}/mark-paid",
        json=payload,
        headers={"X-CSRF-Token": get_csrf(client)},
    )


def create_recurring(
    client: TestClient,
    *,
    category_id: str,
    label: str = "Charge récurrente",
    amount_cents: int | None = 5000,
    scope: str = "personal",
    frequency: str = "monthly",
    start_date: date = date(2025, 1, 15),
    end_date: date | None = None,
    due_day: int | None = 15,
    amount_is_variable: bool = False,
    **extra: Any,
) -> Response:
    payload: dict[str, Any] = {
        "label": label,
        "amount_cents": amount_cents,
        "category_id": category_id,
        "scope": scope,
        "frequency": frequency,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat() if end_date else None,
        "due_day": due_day,
        "amount_is_variable": amount_is_variable,
    }
    payload.update(extra)
    return client.post(
        "/api/v1/recurring-expenses",
        json=payload,
        headers={"X-CSRF-Token": get_csrf(client)},
    )


def list_occurrences(
    client: TestClient,
    recurring_id: str,
    *,
    period: str | None = None,
    status: str | None = None,
) -> Response:
    params: dict[str, str] = {}
    if period is not None:
        params["period"] = period
    if status is not None:
        params["status"] = status
    return client.get(
        f"/api/v1/recurring-expenses/{recurring_id}/occurrences",
        params=params,
    )


def mark_occurrence_paid(
    client: TestClient,
    occurrence_id: str,
    *,
    paid_at: str = "2026-11-05T10:00:00+01:00",
    payment_amount_cents: int | None = None,
    note: str | None = None,
) -> Response:
    payload: dict[str, Any] = {"paid_at": paid_at}
    if payment_amount_cents is not None:
        payload["payment_amount_cents"] = payment_amount_cents
    if note is not None:
        payload["note"] = note
    return client.post(
        f"/api/v1/recurring-occurrences/{occurrence_id}/mark-paid",
        json=payload,
        headers={"X-CSRF-Token": get_csrf(client)},
    )
