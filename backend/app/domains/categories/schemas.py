from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

CategoryName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
]


class CategoryCreate(BaseModel):
    name: CategoryName
    icon: str | None = Field(default=None, max_length=50)
    is_grocery: bool = False


class CategoryUpdate(BaseModel):
    name: CategoryName | None = None
    icon: str | None = Field(default=None, max_length=50)
    is_active: bool | None = None


class CategoryPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    household_id: UUID | None
    name: str
    is_grocery: bool
    icon: str | None
    is_active: bool
