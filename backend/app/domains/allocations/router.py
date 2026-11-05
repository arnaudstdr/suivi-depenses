from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_current_membership,
    get_current_user,
    get_session,
    require_csrf,
    require_owner,
)
from app.api.pagination import Page, PageParams
from app.domains.allocations.contributions import ContributionService
from app.domains.allocations.models import HouseholdContribution
from app.domains.allocations.presenters import (
    allocation_rule_public,
    contribution_public,
)
from app.domains.allocations.schemas import (
    AllocationRulePublic,
    AllocationRuleUpdate,
    ContributionCorrectTransfer,
    ContributionMarkTransferred,
    ContributionPublic,
)
from app.domains.allocations.service import AllocationService
from app.domains.households.models import HouseholdMember
from app.domains.users.models import User

rules_router = APIRouter(
    prefix="/households/me/allocation-rules",
    tags=["allocations"],
)
contributions_router = APIRouter(
    prefix="/households/me/contributions",
    tags=["contributions"],
)
recurring_allocations_router = APIRouter(
    prefix="/recurring-expenses",
    tags=["allocations"],
)


@rules_router.get("", response_model=list[AllocationRulePublic])
def list_allocation_rules(
    membership: HouseholdMember = Depends(get_current_membership),
    db: Session = Depends(get_session),
) -> list[AllocationRulePublic]:
    rules = AllocationService(db).list_rules(membership)
    return [allocation_rule_public(rule) for rule in rules]


@rules_router.put("/default", response_model=AllocationRulePublic)
def update_default_allocation_rule(
    payload: AllocationRuleUpdate,
    membership: HouseholdMember = Depends(require_owner),
    db: Session = Depends(get_session),
    _: None = Depends(require_csrf),
) -> AllocationRulePublic:
    rule = AllocationService(db).set_default_rule(membership, payload.members)
    return allocation_rule_public(rule)


@recurring_allocations_router.put(
    "/{recurring_id}/allocation-rule",
    response_model=AllocationRulePublic,
)
def update_recurring_allocation_rule(
    recurring_id: UUID,
    payload: AllocationRuleUpdate,
    membership: HouseholdMember = Depends(require_owner),
    db: Session = Depends(get_session),
    _: None = Depends(require_csrf),
) -> AllocationRulePublic:
    rule = AllocationService(db).set_recurring_rule(
        membership,
        recurring_id,
        payload.members,
    )
    return allocation_rule_public(rule)


@recurring_allocations_router.delete(
    "/{recurring_id}/allocation-rule",
    status_code=status.HTTP_204_NO_CONTENT,
)
def clear_recurring_allocation_rule(
    recurring_id: UUID,
    membership: HouseholdMember = Depends(require_owner),
    db: Session = Depends(get_session),
    _: None = Depends(require_csrf),
) -> None:
    AllocationService(db).clear_recurring_rule(membership, recurring_id)


@contributions_router.get("", response_model=list[ContributionPublic])
def list_contributions(
    period: str | None = None,
    membership: HouseholdMember = Depends(get_current_membership),
    db: Session = Depends(get_session),
) -> list[ContributionPublic]:
    contributions = ContributionService(db).list_contributions(
        membership,
        period,
    )
    return [contribution_public(item) for item in contributions]


@contributions_router.get("/history", response_model=Page[ContributionPublic])
def list_contributions_history(
    date_from: str | None = None,
    date_to: str | None = None,
    membership: HouseholdMember = Depends(get_current_membership),
    db: Session = Depends(get_session),
    params: PageParams = Depends(),
) -> Page[ContributionPublic]:
    items, total = ContributionService(db).list_history(
        membership,
        date_from=date_from,
        date_to=date_to,
        limit=params.limit,
        offset=params.offset,
    )
    return Page[ContributionPublic](
        items=[contribution_public(item) for item in items],
        total=total,
        limit=params.limit,
        offset=params.offset,
    )


@contributions_router.post(
    "/{contribution_id}/mark-transferred",
    response_model=ContributionPublic,
)
def mark_contribution_transferred(
    contribution_id: UUID,
    payload: ContributionMarkTransferred,
    membership: HouseholdMember = Depends(get_current_membership),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
    _: None = Depends(require_csrf),
) -> ContributionPublic:
    contribution: HouseholdContribution = ContributionService(db).mark_transferred(
        membership,
        user,
        contribution_id,
        payload,
    )
    return contribution_public(contribution)


@contributions_router.post(
    "/{contribution_id}/correct-transfer",
    response_model=ContributionPublic,
)
def correct_contribution_transfer(
    contribution_id: UUID,
    payload: ContributionCorrectTransfer,
    membership: HouseholdMember = Depends(get_current_membership),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
    _: None = Depends(require_csrf),
) -> ContributionPublic:
    contribution: HouseholdContribution = ContributionService(db).correct_transfer(
        membership,
        user,
        contribution_id,
        payload,
    )
    return contribution_public(contribution)
