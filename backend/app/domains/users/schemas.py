from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, StringConstraints

FirstName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    first_name: str
    is_active: bool


class UserUpdate(BaseModel):
    first_name: FirstName
