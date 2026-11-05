import uuid

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.domains.categories.models import Category


def get_usable_category(
    db: Session,
    household_id: uuid.UUID,
    category_id: uuid.UUID,
    *,
    require_active: bool = True,
) -> Category:
    category = db.get(Category, category_id)
    if category is None or (require_active and not category.is_active):
        raise AppError(
            code="invalid_category",
            message="Catégorie introuvable ou inactive.",
            status_code=422,
        )
    if category.household_id is not None and category.household_id != household_id:
        raise AppError(
            code="invalid_category",
            message="Catégorie introuvable ou inactive.",
            status_code=422,
        )
    return category
