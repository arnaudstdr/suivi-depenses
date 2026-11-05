import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domains.imports_exports.models import ImportBatch


class ImportBatchRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def add(self, batch: ImportBatch) -> ImportBatch:
        self._db.add(batch)
        return batch

    def get_for_user(
        self,
        batch_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> ImportBatch | None:
        return self._db.scalar(
            select(ImportBatch).where(
                ImportBatch.id == batch_id,
                ImportBatch.created_by_user_id == user_id,
            )
        )

    def get_for_update(
        self,
        batch_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> ImportBatch | None:
        return self._db.scalar(
            select(ImportBatch)
            .where(
                ImportBatch.id == batch_id,
                ImportBatch.created_by_user_id == user_id,
            )
            .with_for_update()
        )
