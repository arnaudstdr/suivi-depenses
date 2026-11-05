from app.domains.households.models import HouseholdMember
from app.domains.households.schemas import (
    AuthContextResponse,
    HouseholdContextResponse,
    HouseholdMemberPublic,
    HouseholdPublic,
)
from app.domains.households.service import HouseholdContext
from app.domains.users.models import User
from app.domains.users.schemas import UserPublic


def user_public(user: User) -> UserPublic:
    return UserPublic(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        is_active=user.is_active,
    )


def household_public(context: HouseholdContext) -> HouseholdPublic:
    return HouseholdPublic(
        id=context.household.id,
        name=context.household.name,
        currency=context.household.currency,
        timezone=context.household.timezone,
    )


def member_public(member: HouseholdMember) -> HouseholdMemberPublic:
    return HouseholdMemberPublic(
        user_id=member.user_id,
        email=member.user.email,
        first_name=member.user.first_name,
        role=member.role,
        is_active=member.is_active,
    )


def household_context_response(context: HouseholdContext) -> HouseholdContextResponse:
    return HouseholdContextResponse(
        household=household_public(context),
        role=context.membership.role,
        members=[member_public(member) for member in context.members],
    )


def auth_context_response(user: User, context: HouseholdContext) -> AuthContextResponse:
    return AuthContextResponse(
        user=user_public(user),
        household=household_public(context),
        role=context.membership.role,
        members=[member_public(member) for member in context.members],
    )
