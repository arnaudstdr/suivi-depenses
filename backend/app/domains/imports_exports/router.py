from datetime import date
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_app_settings,
    get_current_membership,
    get_current_user,
    get_session,
    require_csrf,
)
from app.core.config import Settings
from app.core.periods import current_period, parse_period
from app.domains.households.models import HouseholdMember
from app.domains.imports_exports.export_service import ExportService
from app.domains.imports_exports.import_service import ImportService
from app.domains.imports_exports.presenters import import_batch_public
from app.domains.imports_exports.schemas import (
    ImportBatchPublic,
    ImportValidateRequest,
)
from app.domains.users.models import User

exports_router = APIRouter(prefix="/exports", tags=["exports"])
imports_router = APIRouter(prefix="/imports", tags=["imports"])


@exports_router.get("/transactions")
def export_transactions(
    format: Literal["csv", "xlsx"] = "csv",
    scope: Literal["all", "personal", "shared"] = "all",
    date_from: date | None = None,
    date_to: date | None = None,
    membership: HouseholdMember = Depends(get_current_membership),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
    settings: Settings = Depends(get_app_settings),
) -> Response:
    export = ExportService(db, settings).export_transactions(
        membership,
        user,
        export_format=format,
        scope=None if scope == "all" else scope,
        date_from=date_from,
        date_to=date_to,
    )
    return _file_response(export.filename, export.content, export.media_type)


@exports_router.get("/contributions")
def export_contributions(
    format: Literal["csv", "xlsx"] = "csv",
    date_from: str | None = None,
    date_to: str | None = None,
    membership: HouseholdMember = Depends(get_current_membership),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
    settings: Settings = Depends(get_app_settings),
) -> Response:
    start = parse_period(date_from)[0] if date_from else date(2000, 1, 1)
    end = parse_period(date_to)[1] if date_to else parse_period(current_period("Europe/Paris"))[1]
    export = ExportService(db, settings).export_contributions(
        membership,
        user,
        export_format=format,
        date_from=start,
        date_to=end,
    )
    return _file_response(export.filename, export.content, export.media_type)


@imports_router.post(
    "/transactions/preview",
    response_model=ImportBatchPublic,
)
async def preview_transactions_import(
    file: UploadFile = File(...),
    scope: Literal["personal", "shared"] = Form("personal"),
    membership: HouseholdMember = Depends(get_current_membership),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
    settings: Settings = Depends(get_app_settings),
    _: None = Depends(require_csrf),
) -> ImportBatchPublic:
    content = await file.read(settings.import_max_bytes + 1)
    batch = ImportService(db, settings).preview(
        membership,
        user,
        filename=file.filename,
        content=content,
        content_type=file.content_type,
        scope=scope,
    )
    return import_batch_public(batch)


@imports_router.get("/{batch_id}", response_model=ImportBatchPublic)
def get_import(
    batch_id: UUID,
    membership: HouseholdMember = Depends(get_current_membership),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
    settings: Settings = Depends(get_app_settings),
) -> ImportBatchPublic:
    batch = ImportService(db, settings).get_batch(membership, user, batch_id)
    return import_batch_public(batch)


@imports_router.post("/{batch_id}/validate", response_model=ImportBatchPublic)
def validate_import(
    batch_id: UUID,
    payload: ImportValidateRequest,
    membership: HouseholdMember = Depends(get_current_membership),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
    settings: Settings = Depends(get_app_settings),
    _: None = Depends(require_csrf),
) -> ImportBatchPublic:
    batch = ImportService(db, settings).validate(
        membership,
        user,
        batch_id,
        duplicate_policy=payload.duplicate_policy,
    )
    return import_batch_public(batch)


@imports_router.post("/{batch_id}/cancel", response_model=ImportBatchPublic)
def cancel_import(
    batch_id: UUID,
    membership: HouseholdMember = Depends(get_current_membership),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
    settings: Settings = Depends(get_app_settings),
    _: None = Depends(require_csrf),
) -> ImportBatchPublic:
    batch = ImportService(db, settings).cancel(membership, user, batch_id)
    return import_batch_public(batch)


def _file_response(filename: str, content: bytes, media_type: str) -> Response:
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )
