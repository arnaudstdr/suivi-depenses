from app.domains.allocations.models import (
    AllocationRule,
    AllocationRuleMember,
    HouseholdContribution,
)
from app.domains.allocations.schemas import (
    AllocationMemberPublic,
    AllocationRulePublic,
    ContributionPublic,
)


def allocation_member_public(
    member: AllocationRuleMember,
) -> AllocationMemberPublic:
    return AllocationMemberPublic(
        user_id=member.user_id,
        email=member.user.email,
        first_name=member.user.first_name,
        percentage=member.percentage,
    )


def allocation_rule_public(rule: AllocationRule) -> AllocationRulePublic:
    return AllocationRulePublic(
        id=rule.id,
        name=rule.name,
        is_default=rule.is_default,
        members=[allocation_member_public(member) for member in rule.members],
    )


def contribution_public(
    contribution: HouseholdContribution,
) -> ContributionPublic:
    return ContributionPublic(
        id=contribution.id,
        household_id=contribution.household_id,
        user_id=contribution.user_id,
        email=contribution.user.email,
        first_name=contribution.user.first_name,
        period=contribution.period_start.strftime("%Y-%m"),
        period_start=contribution.period_start,
        amount_cents=contribution.amount_cents,
        allocation_percentage=contribution.allocation_percentage,
        status=contribution.status,
        transferred_at=contribution.transferred_at,
        transferred_amount_cents=contribution.transferred_amount_cents,
        transaction_id=contribution.transaction_id,
        created_at=contribution.created_at,
    )
