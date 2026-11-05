import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.domains.categories.models import Category


class CategoryRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def list_active(self, household_id: uuid.UUID) -> list[Category]:
        return list(
            self._db.scalars(
                select(Category)
                .where(
                    Category.is_active.is_(True),
                    or_(
                        Category.household_id.is_(None),
                        Category.household_id == household_id,
                    ),
                )
                .order_by(Category.name)
            ).all()
        )

    def get_by_id(self, category_id: uuid.UUID) -> Category | None:
        return self._db.get(Category, category_id)

    def get_by_name(
        self,
        household_id: uuid.UUID,
        name: str,
    ) -> Category | None:
        return self._db.scalar(
            select(Category).where(
                or_(
                    Category.household_id.is_(None),
                    Category.household_id == household_id,
                ),
                func.lower(Category.name) == name.strip().lower(),
            )
        )

    def add(self, category: Category) -> Category:
        self._db.add(category)
        return category
