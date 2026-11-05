from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.security import (
    PASSWORD_MAX_LENGTH,
    validate_password_strength,
)
from app.domains.users.schemas import FirstName


class CsrfResponse(BaseModel):
    csrf_token: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)


class InvitationAcceptRequest(BaseModel):
    email: EmailStr
    first_name: FirstName
    password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return validate_password_strength(value)
