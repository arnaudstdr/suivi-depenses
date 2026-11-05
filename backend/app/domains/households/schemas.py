from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr

from app.domains.users.schemas import UserPublic


class HouseholdPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    currency: str
    timezone: str


class HouseholdMemberPublic(BaseModel):
    user_id: UUID
    email: EmailStr
    first_name: str
    role: str
    is_active: bool


class HouseholdContextResponse(BaseModel):
    household: HouseholdPublic
    role: str
    members: list[HouseholdMemberPublic]


class AuthContextResponse(HouseholdContextResponse):
    user: UserPublic


class InvitationCreate(BaseModel):
    email: EmailStr


class InvitationCreated(BaseModel):
    id: UUID
    email: EmailStr
    role: str
    expires_at: datetime
    token: str
    accept_path: str


class InvitationPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    role: str
    expires_at: datetime
    used_at: datetime | None
    created_at: datetime
