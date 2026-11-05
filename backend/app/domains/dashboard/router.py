from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_membership, get_current_user, get_session
from app.domains.dashboard.schemas import DashboardResponse
from app.domains.dashboard.service import DashboardService
from app.domains.households.models import HouseholdMember
from app.domains.users.models import User

router = APIRouter(prefix="/users/me/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardResponse)
def get_dashboard(
    period: str | None = None,
    membership: HouseholdMember = Depends(get_current_membership),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> DashboardResponse:
    return DashboardService(db).get_dashboard(membership, user, period)
