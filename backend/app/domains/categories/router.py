from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_membership, get_session, require_csrf
from app.domains.categories.models import Category
from app.domains.categories.schemas import CategoryCreate, CategoryPublic, CategoryUpdate
from app.domains.categories.service import CategoryService
from app.domains.households.models import HouseholdMember

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[CategoryPublic])
def list_categories(
    membership: HouseholdMember = Depends(get_current_membership),
    db: Session = Depends(get_session),
) -> list[Category]:
    return CategoryService(db).list_categories(membership)


@router.post("", response_model=CategoryPublic, status_code=status.HTTP_201_CREATED)
def create_category(
    payload: CategoryCreate,
    membership: HouseholdMember = Depends(get_current_membership),
    db: Session = Depends(get_session),
    _: None = Depends(require_csrf),
) -> Category:
    return CategoryService(db).create(
        membership,
        name=payload.name,
        icon=payload.icon,
        is_grocery=payload.is_grocery,
    )


@router.patch("/{category_id}", response_model=CategoryPublic)
def update_category(
    category_id: UUID,
    payload: CategoryUpdate,
    membership: HouseholdMember = Depends(get_current_membership),
    db: Session = Depends(get_session),
    _: None = Depends(require_csrf),
) -> Category:
    return CategoryService(db).update(
        membership,
        category_id,
        name=payload.name,
        icon=payload.icon,
        is_active=payload.is_active,
        set_icon="icon" in payload.model_fields_set,
    )
