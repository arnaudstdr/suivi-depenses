import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class DefaultCategory:
    id: uuid.UUID
    name: str
    icon: str
    is_grocery: bool = False


GROCERY_CATEGORY_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")

DEFAULT_CATEGORIES: tuple[DefaultCategory, ...] = (
    DefaultCategory(
        id=GROCERY_CATEGORY_ID,
        name="Courses / alimentation",
        icon="shopping-cart",
        is_grocery=True,
    ),
    DefaultCategory(
        id=uuid.UUID("00000000-0000-4000-8000-000000000002"),
        name="Logement",
        icon="home",
    ),
    DefaultCategory(
        id=uuid.UUID("00000000-0000-4000-8000-000000000003"),
        name="Énergie",
        icon="zap",
    ),
    DefaultCategory(
        id=uuid.UUID("00000000-0000-4000-8000-000000000004"),
        name="Transport",
        icon="car",
    ),
    DefaultCategory(
        id=uuid.UUID("00000000-0000-4000-8000-000000000005"),
        name="Santé",
        icon="heart-pulse",
    ),
    DefaultCategory(
        id=uuid.UUID("00000000-0000-4000-8000-000000000006"),
        name="Abonnements",
        icon="repeat",
    ),
    DefaultCategory(
        id=uuid.UUID("00000000-0000-4000-8000-000000000007"),
        name="Loisirs",
        icon="gamepad-2",
    ),
    DefaultCategory(
        id=uuid.UUID("00000000-0000-4000-8000-000000000008"),
        name="Divers",
        icon="more-horizontal",
    ),
)
