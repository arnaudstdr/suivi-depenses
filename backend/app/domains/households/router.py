from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_app_settings,
    get_current_membership,
    get_session,
    require_csrf,
    require_owner,
)
from app.api.presenters import household_context_response
from app.core.config import Settings
from app.domains.auth.models import Invitation
from app.domains.households.models import HouseholdMember
from app.domains.households.schemas import (
    HouseholdContextResponse,
    InvitationCreate,
    InvitationCreated,
    InvitationPublic,
)
from app.domains.households.service import HouseholdService

router = APIRouter(prefix="/households", tags=["households"])


@router.get("/me", response_model=HouseholdContextResponse)
def get_my_household(
    membership: HouseholdMember = Depends(get_current_membership),
    db: Session = Depends(get_session),
    settings: Settings = Depends(get_app_settings),
) -> HouseholdContextResponse:
    context = HouseholdService(db, settings).get_context(membership)
    return household_context_response(context)


@router.post(
    "/me/invitations",
    response_model=InvitationCreated,
    status_code=status.HTTP_201_CREATED,
)
def create_invitation(
    payload: InvitationCreate,
    membership: HouseholdMember = Depends(require_owner),
    db: Session = Depends(get_session),
    settings: Settings = Depends(get_app_settings),
    _: None = Depends(require_csrf),
) -> InvitationCreated:
    creation = HouseholdService(db, settings).create_invitation(
        membership,
        str(payload.email),
    )
    invitation = creation.invitation
    return InvitationCreated(
        id=invitation.id,
        email=invitation.email,
        role=invitation.role,
        expires_at=invitation.expires_at,
        token=creation.raw_token,
        accept_path=f"{settings.api_v1_prefix}/invitations/{creation.raw_token}/accept",
    )


@router.get("/me/invitations", response_model=list[InvitationPublic])
def list_invitations(
    membership: HouseholdMember = Depends(require_owner),
    db: Session = Depends(get_session),
    settings: Settings = Depends(get_app_settings),
) -> list[Invitation]:
    return HouseholdService(db, settings).list_invitations(membership)
