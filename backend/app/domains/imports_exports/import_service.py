import hashlib
import uuid
from collections.abc import Callable
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import PurePath
from typing import Any

from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.core.config import Settings
from app.core.errors import AppError
from app.core.request_context import request_id_var
from app.domains.audit.repository import AuditRepository
from app.domains.categories.models import Category
from app.domains.categories.repository import CategoryRepository
from app.domains.households.models import HouseholdMember
from app.domains.imports_exports.formats import import_format, parse_import_file
from app.domains.imports_exports.models import ImportBatch
from app.domains.imports_exports.repository import ImportBatchRepository
from app.domains.imports_exports.schemas import ImportPreviewRow
from app.domains.notifications.service import NotificationService
from app.domains.transactions.repository import TransactionRepository
from app.domains.transactions.schemas import TransactionCreate
from app.domains.transactions.service import TransactionService
from app.domains.users.models import User

PREVIEW_VALID = "valid"
PREVIEW_DUPLICATE = "duplicate"
PREVIEW_ERROR = "error"


class ImportService:
    def __init__(
        self,
        db: Session,
        settings: Settings,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._db = db
        self._settings = settings
        self._now = now or utcnow
        self._imports = ImportBatchRepository(db)
        self._transactions = TransactionRepository(db)
        self._categories = CategoryRepository(db)
        self._audit = AuditRepository(db)

    def preview(
        self,
        membership: HouseholdMember,
        user: User,
        *,
        filename: str | None,
        content: bytes,
        content_type: str | None,
        scope: str,
    ) -> ImportBatch:
        if scope not in {"personal", "shared"}:
            raise AppError(
                code="invalid_import_scope",
                message="Le périmètre doit être personal ou shared.",
                status_code=422,
            )
        if len(content) > self._settings.import_max_bytes:
            raise AppError(
                code="import_too_large",
                message=(
                    f"Le fichier dépasse la limite de {self._settings.import_max_bytes} octets."
                ),
                status_code=422,
            )

        source_format = import_format(filename)
        raw_rows = parse_import_file(
            content=content,
            source_format=source_format,
            max_rows=self._settings.import_max_rows,
        )
        rows = self._prepare_rows(
            membership,
            user,
            raw_rows,
            scope,
        )
        now = self._now()
        batch = ImportBatch(
            household_id=membership.household_id,
            created_by_user_id=user.id,
            target_type="transactions",
            scope=scope,
            original_filename=_sanitize_filename(filename),
            source_format=source_format,
            content_type=content_type,
            checksum=hashlib.sha256(content).hexdigest(),
            status="preview",
            total_rows=len(rows),
            valid_rows=_count_status(rows, PREVIEW_VALID),
            duplicate_rows=_count_status(rows, PREVIEW_DUPLICATE),
            error_rows=_count_status(rows, PREVIEW_ERROR),
            preview=rows,
            expires_at=now + timedelta(seconds=self._settings.import_preview_ttl_seconds),
        )
        self._imports.add(batch)
        self._db.flush()

        self._audit.add(
            occurred_at=now,
            action="import.previewed",
            entity_type="import_batch",
            entity_id=batch.id,
            actor_user_id=user.id,
            household_id=membership.household_id,
            details={
                "format": source_format,
                "scope": scope,
                "total_rows": batch.total_rows,
                "valid_rows": batch.valid_rows,
                "duplicate_rows": batch.duplicate_rows,
                "error_rows": batch.error_rows,
            },
            request_id=request_id_var.get(),
        )
        self._db.commit()
        return batch

    def get_batch(
        self,
        membership: HouseholdMember,
        user: User,
        batch_id: uuid.UUID,
    ) -> ImportBatch:
        batch = self._imports.get_for_user(batch_id, user.id)
        if batch is None or batch.household_id != membership.household_id:
            raise self._not_found()
        return batch

    def validate(
        self,
        membership: HouseholdMember,
        user: User,
        batch_id: uuid.UUID,
        *,
        duplicate_policy: str,
    ) -> ImportBatch:
        if duplicate_policy not in {"skip", "import"}:
            raise AppError(
                code="invalid_duplicate_policy",
                message="La politique de doublon doit être skip ou import.",
                status_code=422,
            )
        batch = self._imports.get_for_update(batch_id, user.id)
        if batch is None or batch.household_id != membership.household_id:
            raise self._not_found()
        if batch.status == "validated":
            return batch
        if batch.status == "cancelled":
            raise AppError(
                code="import_cancelled",
                message="Cet import a été annulé.",
                status_code=409,
            )
        now = self._now()
        if batch.expires_at <= now:
            raise AppError(
                code="import_expired",
                message="La prévisualisation a expiré. Importez à nouveau le fichier.",
                status_code=409,
            )

        inserted = 0
        skipped_duplicates = 0
        skipped_errors = 0
        transaction_service = TransactionService(self._db, self._now)
        for row in batch.preview:
            status = row["status"]
            if status == PREVIEW_ERROR:
                skipped_errors += 1
                continue
            if status == PREVIEW_DUPLICATE and duplicate_policy == "skip":
                skipped_duplicates += 1
                continue

            transaction_service.create(
                membership,
                user,
                TransactionCreate(
                    label=row["label"],
                    amount_cents=row["amount_cents"],
                    transaction_date=date.fromisoformat(row["transaction_date"]),
                    category_id=uuid.UUID(row["category_id"]),
                    scope=batch.scope,
                    transaction_type="expense",
                    notes=row["notes"],
                ),
                commit=False,
            )
            inserted += 1

        batch.status = "validated"
        batch.validated_at = now
        batch.result = {
            "inserted_rows": inserted,
            "skipped_duplicates": skipped_duplicates,
            "skipped_errors": skipped_errors,
        }
        self._audit.add(
            occurred_at=now,
            action="import.validated",
            entity_type="import_batch",
            entity_id=batch.id,
            actor_user_id=user.id,
            household_id=membership.household_id,
            details={
                "inserted_rows": inserted,
                "skipped_duplicates": skipped_duplicates,
                "skipped_errors": skipped_errors,
            },
            request_id=request_id_var.get(),
        )
        NotificationService(self._db, self._now).notify(
            user_id=user.id,
            notification_type="import_completed",
            title="Import terminé",
            body=f"{inserted} dépense(s) importée(s).",
            household_id=membership.household_id,
            entity_type="import_batch",
            entity_id=batch.id,
            dedupe_key=f"import_completed:{batch.id}",
            commit=False,
        )
        self._db.commit()
        return batch

    def cancel(
        self,
        membership: HouseholdMember,
        user: User,
        batch_id: uuid.UUID,
    ) -> ImportBatch:
        batch = self._imports.get_for_update(batch_id, user.id)
        if batch is None or batch.household_id != membership.household_id:
            raise self._not_found()
        if batch.status == "validated":
            raise AppError(
                code="import_already_validated",
                message="Un import validé ne peut plus être annulé.",
                status_code=409,
            )
        if batch.status == "cancelled":
            return batch
        batch.status = "cancelled"
        self._audit.add(
            occurred_at=self._now(),
            action="import.cancelled",
            entity_type="import_batch",
            entity_id=batch.id,
            actor_user_id=user.id,
            household_id=membership.household_id,
            request_id=request_id_var.get(),
        )
        self._db.commit()
        return batch

    def _prepare_rows(
        self,
        membership: HouseholdMember,
        user: User,
        raw_rows: list[dict[str, Any]],
        scope: str,
    ) -> list[dict[str, object]]:
        parsed: list[dict[str, Any]] = []
        valid_dates: list[date] = []
        for raw in raw_rows:
            errors = list(raw.get("errors", []))
            raw_date = raw.get("date")
            raw_label = raw.get("label")
            raw_amount = raw.get("amount")
            raw_category = raw.get("category")
            raw_notes = raw.get("notes")

            transaction_date = _parse_date(raw_date) if isinstance(raw_date, str) else None
            if transaction_date is None and not errors:
                errors.append("La date est invalide (attendu YYYY-MM-DD ou JJ/MM/AAAA).")
            label = str(raw_label).strip() if raw_label is not None else ""
            if not label:
                errors.append("Le libellé est obligatoire.")
            elif len(label) > 255:
                errors.append("Le libellé dépasse 255 caractères.")
            amount_cents = _parse_amount(raw_amount)
            if amount_cents is None:
                errors.append("Le montant est invalide ou négatif.")
            notes_value: str | None = str(raw_notes).strip() if raw_notes is not None else None
            notes = notes_value or None
            if notes is not None and len(notes) > 2000:
                errors.append("Les notes dépassent 2000 caractères.")
            category = self._resolve_category(
                membership,
                str(raw_category) if raw_category is not None else "",
                errors,
            )

            if transaction_date is not None:
                valid_dates.append(transaction_date)
            parsed.append(
                {
                    "row_number": int(raw["row_number"]),
                    "transaction_date": transaction_date,
                    "label": label or None,
                    "amount_cents": amount_cents,
                    "category": category,
                    "category_name": category.name if category is not None else None,
                    "notes": notes,
                    "errors": errors,
                }
            )

        existing_keys: set[tuple[date, int, str, uuid.UUID]] = set()
        if valid_dates:
            existing_keys = self._transactions.duplicate_keys(
                user_id=user.id,
                household_id=membership.household_id,
                scope=scope,
                date_from=min(valid_dates),
                date_to=max(valid_dates),
            )

        seen: set[tuple[date, int, str, uuid.UUID]] = set()
        rows: list[dict[str, Any]] = []
        for item in parsed:
            errors = list(item.pop("errors"))
            category = item.pop("category")
            transaction_date = item["transaction_date"]
            amount_cents = item["amount_cents"]
            label = item["label"]
            status = PREVIEW_ERROR
            if (
                not errors
                and isinstance(transaction_date, date)
                and isinstance(amount_cents, int)
                and isinstance(label, str)
                and isinstance(category, Category)
            ):
                key = (
                    transaction_date,
                    amount_cents,
                    label.casefold(),
                    category.id,
                )
                if key in seen or key in existing_keys:
                    status = PREVIEW_DUPLICATE
                else:
                    status = PREVIEW_VALID
                    seen.add(key)
            rows.append(
                {
                    "row_number": item["row_number"],
                    "transaction_date": (
                        transaction_date.isoformat() if isinstance(transaction_date, date) else None
                    ),
                    "label": label,
                    "amount_cents": amount_cents,
                    "category_id": str(category.id) if category is not None else None,
                    "category_name": item["category_name"],
                    "notes": item["notes"],
                    "status": status,
                    "errors": errors,
                }
            )
        return rows

    def _resolve_category(
        self,
        membership: HouseholdMember,
        name: str,
        errors: list[str],
    ) -> Category | None:
        if not name.strip():
            errors.append("La catégorie est obligatoire.")
            return None
        category = self._categories.get_by_name(membership.household_id, name)
        if category is None:
            errors.append(f"Catégorie inconnue : {name}.")
            return None
        if not category.is_active:
            errors.append(f"Catégorie inactive : {name}.")
            return None
        return category

    @staticmethod
    def _not_found() -> AppError:
        return AppError(
            code="not_found",
            message="Import introuvable.",
            status_code=404,
        )


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        try:
            return datetime.strptime(value.strip(), "%d/%m/%Y").date()
        except ValueError:
            return None


def _parse_amount(value: object) -> int | None:
    if value is None:
        return None
    cleaned = (
        str(value)
        .replace("\u202f", "")
        .replace("\xa0", "")
        .replace(" ", "")
        .replace("€", "")
        .replace("EUR", "")
        .strip()
    )
    if not cleaned:
        return None
    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    else:
        cleaned = cleaned.replace(",", ".")
    try:
        amount = Decimal(cleaned)
    except InvalidOperation:
        return None
    if not amount.is_finite():
        return None
    quantized = amount.quantize(Decimal("0.01"))
    if quantized != amount:
        return None
    cents = int(quantized * 100)
    return cents if cents > 0 else None


def _count_status(rows: list[dict[str, Any]], status: str) -> int:
    return sum(1 for row in rows if row["status"] == status)


def _sanitize_filename(filename: str | None) -> str | None:
    if not filename:
        return None
    sanitized = PurePath(filename.replace("\\", "/")).name.strip()
    return sanitized[:255] or None


def preview_rows(batch: ImportBatch) -> list[ImportPreviewRow]:
    return [ImportPreviewRow.model_validate(row) for row in batch.preview]
