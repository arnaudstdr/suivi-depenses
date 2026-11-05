import csv
import io
from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook, load_workbook
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.domains.imports_exports.models import ImportBatch
from app.domains.transactions.models import Transaction
from tests.auth_helpers import get_csrf, login, setup_two_member_household
from tests.finance_helpers import category_id, create_transaction

pytestmark = pytest.mark.integration

CSV_HEADER = "date,label,amount,category,notes\n"


def _upload_preview(
    client: TestClient,
    *,
    content: bytes,
    filename: str = "depenses.csv",
    scope: str = "personal",
    content_type: str = "text/csv",
):
    return client.post(
        "/api/v1/imports/transactions/preview",
        files={"file": (filename, content, content_type)},
        data={"scope": scope},
        headers={"X-CSRF-Token": get_csrf(client)},
    )


def _validate(client: TestClient, batch_id: str, policy: str = "skip"):
    return client.post(
        f"/api/v1/imports/{batch_id}/validate",
        json={"duplicate_policy": policy},
        headers={"X-CSRF-Token": get_csrf(client)},
    )


def _csv_rows(content: bytes) -> list[dict[str, str]]:
    return list(
        csv.DictReader(
            io.StringIO(content.decode("utf-8-sig")),
            delimiter=";",
        )
    )


def _login_member(client: TestClient) -> None:
    client.cookies.clear()
    assert (
        login(
            client,
            email="member@example.com",
            password="another-strong-password",
        ).status_code
        == 200
    )


def test_transactions_export_respects_permissions(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    setup_two_member_household(client, db_session, test_settings)
    transport = category_id(client, "Transport")
    loisirs = category_id(client, "Loisirs")
    logement = category_id(client, "Logement")
    assert (
        create_transaction(
            client,
            category_id=transport,
            label="Essence",
            amount_cents=5000,
        ).status_code
        == 201
    )
    assert (
        create_transaction(
            client,
            category_id=logement,
            label="Loyer",
            amount_cents=7000,
            scope="shared",
        ).status_code
        == 201
    )
    _login_member(client)
    assert (
        create_transaction(
            client,
            category_id=loisirs,
            label="Cinéma",
            amount_cents=3000,
        ).status_code
        == 201
    )
    client.cookies.clear()
    assert login(client).status_code == 200

    response = client.get("/api/v1/exports/transactions", params={"format": "csv"})

    assert response.status_code == 200, response.text
    rows = _csv_rows(response.content)
    assert {row["label"] for row in rows} == {"Essence", "Loyer"}
    assert response.headers["content-type"].startswith("text/csv")


def test_transactions_export_filters_and_xlsx(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    setup_two_member_household(client, db_session, test_settings)
    transport = category_id(client, "Transport")
    assert (
        create_transaction(
            client,
            category_id=transport,
            label="Janvier",
            amount_cents=1000,
            transaction_date=date(2025, 1, 10),
        ).status_code
        == 201
    )
    assert (
        create_transaction(
            client,
            category_id=transport,
            label="Février",
            amount_cents=2000,
            transaction_date=date(2025, 2, 10),
        ).status_code
        == 201
    )

    response = client.get(
        "/api/v1/exports/transactions",
        params={
            "format": "xlsx",
            "date_from": "2025-02-01",
            "date_to": "2025-02-28",
        },
    )

    assert response.status_code == 200, response.text
    workbook = load_workbook(io.BytesIO(response.content), read_only=True)
    sheet = workbook.active
    values = list(sheet.iter_rows(values_only=True))
    workbook.close()
    assert values[0][0] == "date"
    assert len(values) == 2
    assert values[1][1] == "Février"


def test_export_neutralizes_spreadsheet_formulas(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    setup_two_member_household(client, db_session, test_settings)
    transport = category_id(client, "Transport")
    assert (
        create_transaction(
            client,
            category_id=transport,
            label='=HYPERLINK("https://example.com")',
            amount_cents=1000,
        ).status_code
        == 201
    )

    response = client.get("/api/v1/exports/transactions", params={"format": "csv"})

    assert response.status_code == 200
    rows = _csv_rows(response.content)
    assert rows[0]["label"].startswith("'=")


def test_contributions_export_contains_household_members(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    setup_two_member_household(client, db_session, test_settings)
    assert client.get("/api/v1/households/me/contributions").status_code == 200

    response = client.get("/api/v1/exports/contributions", params={"format": "csv"})

    assert response.status_code == 200, response.text
    rows = _csv_rows(response.content)
    assert len(rows) == 2
    assert {row["member_email"] for row in rows} == {
        "owner@example.com",
        "member@example.com",
    }


def test_import_preview_detects_valid_duplicate_and_error_rows(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    setup_two_member_household(client, db_session, test_settings)
    transport = category_id(client, "Transport")
    assert (
        create_transaction(
            client,
            category_id=transport,
            label="Déjà là",
            amount_cents=1000,
            transaction_date=date(2025, 1, 11),
        ).status_code
        == 201
    )
    content = (
        CSV_HEADER
        + "2025-01-10,Café,4.50,Loisirs,\n"
        + "2025-01-11,Déjà là,10.00,Transport,\n"
        + "2025-01-12,Erreur,-2.00,Transport,\n"
    ).encode()

    response = _upload_preview(client, content=content)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "preview"
    assert payload["total_rows"] == 3
    assert payload["valid_rows"] == 1
    assert payload["duplicate_rows"] == 1
    assert payload["error_rows"] == 1
    statuses = [row["status"] for row in payload["rows"]]
    assert statuses == ["valid", "duplicate", "error"]


def test_import_validation_is_atomic_and_idempotent(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    setup_two_member_household(client, db_session, test_settings)
    transport = category_id(client, "Transport")
    assert (
        create_transaction(
            client,
            category_id=transport,
            label="Déjà là",
            amount_cents=1000,
            transaction_date=date(2025, 1, 11),
        ).status_code
        == 201
    )
    content = (
        CSV_HEADER
        + "2025-01-10,Café,4.50,Loisirs,\n"
        + "2025-01-11,Déjà là,10.00,Transport,\n"
        + "2025-01-12,Erreur,-2.00,Transport,\n"
    ).encode()
    batch = _upload_preview(client, content=content).json()

    first = _validate(client, batch["id"])
    second = _validate(client, batch["id"])

    assert first.status_code == 200, first.text
    assert first.json()["status"] == "validated"
    assert first.json()["result"] == {
        "inserted_rows": 1,
        "skipped_duplicates": 1,
        "skipped_errors": 1,
    }
    assert second.json()["result"] == first.json()["result"]

    db_session.expire_all()
    assert (
        db_session.scalar(
            select(func.count()).select_from(Transaction).where(Transaction.label == "Café")
        )
        == 1
    )
    assert (
        db_session.scalar(
            select(func.count()).select_from(Transaction).where(Transaction.label == "Déjà là")
        )
        == 1
    )


def test_duplicate_can_be_imported_explicitly(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    setup_two_member_household(client, db_session, test_settings)
    transport = category_id(client, "Transport")
    assert (
        create_transaction(
            client,
            category_id=transport,
            label="Déjà là",
            amount_cents=1000,
            transaction_date=date(2025, 1, 11),
        ).status_code
        == 201
    )
    content = (CSV_HEADER + "2025-01-11,Déjà là,10.00,Transport,\n").encode()
    batch = _upload_preview(client, content=content).json()
    assert batch["duplicate_rows"] == 1

    response = _validate(client, batch["id"], policy="import")

    assert response.status_code == 200, response.text
    assert response.json()["result"]["inserted_rows"] == 1
    db_session.expire_all()
    assert (
        db_session.scalar(
            select(func.count()).select_from(Transaction).where(Transaction.label == "Déjà là")
        )
        == 2
    )


def test_xlsx_import_is_supported(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    setup_two_member_household(client, db_session, test_settings)
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["date", "label", "amount", "category", "notes"])
    sheet.append(["2025-03-04", "XLSX", 12.34, "Loisirs", "test"])
    buffer = io.BytesIO()
    workbook.save(buffer)

    response = _upload_preview(
        client,
        content=buffer.getvalue(),
        filename="depenses.xlsx",
        content_type=("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["valid_rows"] == 1
    assert payload["rows"][0]["amount_cents"] == 1234


def test_shared_grocery_import_consumes_grocery_budget(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    setup_two_member_household(client, db_session, test_settings)
    grocery = next(
        category for category in client.get("/api/v1/categories").json() if category["is_grocery"]
    )
    content = (CSV_HEADER + f"2025-04-05,Courses,42.00,{grocery['name']},\n").encode()
    batch = _upload_preview(client, content=content, scope="shared").json()

    validated = _validate(client, batch["id"])

    assert validated.status_code == 200, validated.text
    budget = client.get(
        "/api/v1/households/me/grocery-budget",
        params={"period": "2025-04"},
    ).json()
    assert budget["spent_cents"] == 4200
    assert budget["remaining_cents"] == 49000 - 4200


def test_import_batch_is_private_to_its_creator(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    setup_two_member_household(client, db_session, test_settings)
    content = (CSV_HEADER + "2025-01-10,Café,4.50,Loisirs,\n").encode()
    batch = _upload_preview(client, content=content).json()

    _login_member(client)

    assert client.get(f"/api/v1/imports/{batch['id']}").status_code == 404


def test_import_requires_csrf_and_valid_file(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    setup_two_member_household(client, db_session, test_settings)
    content = (CSV_HEADER + "2025-01-10,Café,4.50,Loisirs,\n").encode()

    no_csrf = client.post(
        "/api/v1/imports/transactions/preview",
        files={"file": ("depenses.csv", content, "text/csv")},
        data={"scope": "personal"},
    )
    invalid = _upload_preview(
        client,
        content=b"not a csv",
        filename="depenses.txt",
    )

    assert no_csrf.status_code == 403
    assert invalid.status_code == 422
    assert invalid.json()["code"] == "unsupported_import_format"


def test_expired_preview_cannot_be_validated(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    setup_two_member_household(client, db_session, test_settings)
    content = (CSV_HEADER + "2025-01-10,Café,4.50,Loisirs,\n").encode()
    batch = _upload_preview(client, content=content).json()

    stored = db_session.get(ImportBatch, batch["id"])
    assert stored is not None
    stored.expires_at = datetime.now(stored.expires_at.tzinfo) - timedelta(minutes=1)
    db_session.commit()

    response = _validate(client, batch["id"])

    assert response.status_code == 409
    assert response.json()["code"] == "import_expired"


def test_import_rejects_too_many_rows(
    client: TestClient,
    db_session: Session,
    test_settings: Settings,
) -> None:
    setup_two_member_household(client, db_session, test_settings)
    lines = [CSV_HEADER]
    for index in range(1001):
        lines.append(f"2025-01-10,Ligne {index},1.00,Loisirs,\n")
    content = "".join(lines).encode()

    response = _upload_preview(client, content=content)

    assert response.status_code == 422
    assert response.json()["code"] == "import_too_many_rows"
