from app.domains.imports_exports.import_service import preview_rows
from app.domains.imports_exports.models import ImportBatch
from app.domains.imports_exports.schemas import ImportBatchPublic, ImportResult


def import_batch_public(batch: ImportBatch) -> ImportBatchPublic:
    return ImportBatchPublic(
        id=batch.id,
        status=batch.status,
        scope=batch.scope,
        source_format=batch.source_format,
        original_filename=batch.original_filename,
        total_rows=batch.total_rows,
        valid_rows=batch.valid_rows,
        duplicate_rows=batch.duplicate_rows,
        error_rows=batch.error_rows,
        rows=preview_rows(batch),
        result=(ImportResult.model_validate(batch.result) if batch.result is not None else None),
        expires_at=batch.expires_at,
        validated_at=batch.validated_at,
        created_at=batch.created_at,
    )
