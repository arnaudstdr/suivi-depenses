import uuid
from collections.abc import Callable
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.core.errors import AppError
from app.core.request_context import request_id_var
from app.domains.audit.repository import AuditRepository
from app.domains.categories.models import Category
from app.domains.categories.repository import CategoryRepository
from app.domains.households.models import HouseholdMember


class CategoryService:
    def __init__(
        self,
        db: Session,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._db = db
        self._now = now or utcnow
        self._categories = CategoryRepository(db)
        self._audit = AuditRepository(db)

    def list_categories(self, membership: HouseholdMember) -> list[Category]:
        return self._categories.list_active(membership.household_id)

    def create(
        self,
        membership: HouseholdMember,
        *,
        name: str,
        icon: str | None,
        is_grocery: bool,
    ) -> Category:
        if self._categories.get_by_name(membership.household_id, name) is not None:
            raise AppError(
                code="category_exists",
                message="Une catégorie porte déjà ce nom.",
                status_code=409,
            )

        category = Category(
            household_id=membership.household_id,
            name=name.strip(),
            category_type="expense",
            is_grocery=is_grocery,
            icon=icon,
            is_active=True,
        )
        self._categories.add(category)
        self._db.flush()

        self._audit.add(
            occurred_at=self._now(),
            action="category.created",
            entity_type="category",
            entity_id=category.id,
            actor_user_id=membership.user_id,
            household_id=membership.household_id,
            request_id=request_id_var.get(),
        )
        self._db.commit()
        return category

    def update(
        self,
        membership: HouseholdMember,
        category_id: uuid.UUID,
        *,
        name: str | None,
        icon: str | None,
        is_active: bool | None,
        set_icon: bool,
    ) -> Category:
        category = self._categories.get_by_id(category_id)
        if category is None or category.household_id != membership.household_id:
            raise AppError(
                code="not_found",
                message="Catégorie introuvable.",
                status_code=404,
            )

        if name is not None and name.strip().lower() != category.name.lower():
            existing = self._categories.get_by_name(membership.household_id, name)
            if existing is not None and existing.id != category.id:
                raise AppError(
                    code="category_exists",
                    message="Une catégorie porte déjà ce nom.",
                    status_code=409,
                )
            category.name = name.strip()

        if set_icon:
            category.icon = icon
        if is_active is not None:
            category.is_active = is_active

        self._audit.add(
            occurred_at=self._now(),
            action="category.updated",
            entity_type="category",
            entity_id=category.id,
            actor_user_id=membership.user_id,
            household_id=membership.household_id,
            request_id=request_id_var.get(),
        )
        self._db.commit()
        return category
