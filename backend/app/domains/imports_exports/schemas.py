from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class ImportPreviewRow(BaseModel):
    row_number: int
    transaction_date: date | None
    label: str | None
    amount_cents: int | None
    category_id: UUID | None
    category_name: str | None
    notes: str | None
    status: Literal["valid", "duplicate", "error"]
    errors: list[str]


class ImportResult(BaseModel):
    inserted_rows: int
    skipped_duplicates: int
    skipped_errors: int


class ImportBatchPublic(BaseModel):
    id: UUID
    status: str
    scope: str
    source_format: str
    original_filename: str | None
    total_rows: int
    valid_rows: int
    duplicate_rows: int
    error_rows: int
    rows: list[ImportPreviewRow]
    result: ImportResult | None
    expires_at: datetime
    validated_at: datetime | None
    created_at: datetime


class ImportValidateRequest(BaseModel):
    duplicate_policy: Literal["skip", "import"] = "skip"
