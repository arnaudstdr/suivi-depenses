from sqlalchemy.orm import Session

from app.domains.categories.constants import DEFAULT_CATEGORIES
from app.domains.categories.models import Category


def ensure_default_categories(db: Session) -> None:
    """Insère les catégories globales manquantes, de façon idempotente."""
    added = False
    for default in DEFAULT_CATEGORIES:
        if db.get(Category, default.id) is None:
            db.add(
                Category(
                    id=default.id,
                    household_id=None,
                    name=default.name,
                    category_type="expense",
                    is_grocery=default.is_grocery,
                    icon=default.icon,
                    is_active=True,
                )
            )
            added = True
    if added:
        db.flush()
