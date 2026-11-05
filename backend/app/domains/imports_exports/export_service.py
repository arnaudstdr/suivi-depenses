from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.core.config import Settings
from app.core.errors import AppError
from app.core.request_context import request_id_var
from app.domains.allocations.repository import AllocationRepository
from app.domains.audit.repository import AuditRepository
from app.domains.households.models import HouseholdMember
from app.domains.imports_exports.formats import build_csv, build_xlsx
from app.domains.transactions.repository import TransactionRepository
from app.domains.users.models import User

TRANSACTION_HEADERS = [
    "date",
    "label",
    "amount",
    "category",
    "scope",
    "type",
    "paid_at",
    "notes",
]
CONTRIBUTION_HEADERS = [
    "period",
    "member_email",
    "member_first_name",
    "amount",
    "allocation_percentage",
    "status",
    "transferred_at",
    "transferred_amount",
]


@dataclass(frozen=True)
class FileExport:
    filename: str
    content: bytes
    media_type: str


class ExportService:
    def __init__(
        self,
        db: Session,
        settings: Settings,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._db = db
        self._settings = settings
        self._now = now or utcnow
        self._transactions = TransactionRepository(db)
        self._allocations = AllocationRepository(db)
        self._audit = AuditRepository(db)

    def export_transactions(
        self,
        membership: HouseholdMember,
        user: User,
        *,
        export_format: str,
        scope: str | None,
        date_from: date | None,
        date_to: date | None,
    ) -> FileExport:
        self._validate_dates(date_from, date_to)
        rows, total = self._transactions.list_for_member(
            user_id=user.id,
            household_id=membership.household_id,
            scope=scope,
            category_id=None,
            date_from=date_from,
            date_to=date_to,
            status=None,
            search=None,
            limit=self._settings.export_max_rows + 1,
            offset=0,
        )
        self._assert_export_size(total)

        values = [
            [
                transaction.transaction_date.isoformat(),
                transaction.label,
                _euros(transaction.amount_cents),
                transaction.category.name,
                transaction.scope,
                transaction.transaction_type,
                transaction.paid_at.isoformat() if transaction.paid_at else "",
                transaction.notes or "",
            ]
            for transaction in rows
        ]
        self._audit.add(
            occurred_at=self._now(),
            action="export.transactions",
            entity_type="transaction",
            actor_user_id=user.id,
            household_id=membership.household_id,
            details={
                "rows": len(values),
                "format": export_format,
                "scope": scope,
            },
            request_id=request_id_var.get(),
        )
        self._db.commit()
        return _build_export(
            export_format,
            "transactions",
            TRANSACTION_HEADERS,
            values,
        )

    def export_contributions(
        self,
        membership: HouseholdMember,
        user: User,
        *,
        export_format: str,
        date_from: date,
        date_to: date,
    ) -> FileExport:
        self._validate_dates(date_from, date_to)
        rows, total = self._allocations.list_contributions_history(
            membership.household_id,
            date_from=date_from,
            date_to=date_to,
            limit=self._settings.export_max_rows + 1,
            offset=0,
        )
        self._assert_export_size(total)

        values = [
            [
                contribution.period_start.strftime("%Y-%m"),
                contribution.user.email,
                contribution.user.first_name,
                _euros(contribution.amount_cents),
                str(contribution.allocation_percentage),
                contribution.status,
                contribution.transferred_at.isoformat() if contribution.transferred_at else "",
                _euros(contribution.transferred_amount_cents)
                if contribution.transferred_amount_cents is not None
                else "",
            ]
            for contribution in rows
        ]
        self._audit.add(
            occurred_at=self._now(),
            action="export.contributions",
            entity_type="household_contribution",
            actor_user_id=user.id,
            household_id=membership.household_id,
            details={"rows": len(values), "format": export_format},
            request_id=request_id_var.get(),
        )
        self._db.commit()
        return _build_export(
            export_format,
            "contributions",
            CONTRIBUTION_HEADERS,
            values,
        )

    def _assert_export_size(self, total: int) -> None:
        if total > self._settings.export_max_rows:
            raise AppError(
                code="export_too_large",
                message=(
                    "L'export dépasse la limite de "
                    f"{self._settings.export_max_rows} lignes. Affinez les filtres."
                ),
                status_code=422,
            )

    @staticmethod
    def _validate_dates(date_from: date | None, date_to: date | None) -> None:
        if date_from is not None and date_to is not None and date_from > date_to:
            raise AppError(
                code="invalid_date_range",
                message="La date de début doit précéder la date de fin.",
                status_code=422,
            )


def _build_export(
    export_format: str,
    name: str,
    headers: list[str],
    rows: list[list[str]],
) -> FileExport:
    if export_format == "csv":
        return FileExport(
            filename=f"{name}-{date.today().isoformat()}.csv",
            content=build_csv(headers, rows),
            media_type="text/csv; charset=utf-8",
        )
    if export_format == "xlsx":
        return FileExport(
            filename=f"{name}-{date.today().isoformat()}.xlsx",
            content=build_xlsx(headers, rows),
            media_type=("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        )
    raise AppError(
        code="unsupported_export_format",
        message="Seuls les formats CSV et XLSX sont acceptés.",
        status_code=422,
    )


def _euros(cents: int) -> str:
    return format(Decimal(cents) / Decimal(100), ".2f")
