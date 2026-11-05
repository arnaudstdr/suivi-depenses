import uuid
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.core.errors import AppError
from app.core.request_context import request_id_var
from app.domains.allocations.models import AllocationRule, AllocationRuleMember
from app.domains.allocations.repository import AllocationRepository
from app.domains.allocations.schemas import AllocationMemberInput
from app.domains.audit.repository import AuditRepository
from app.domains.households.models import HouseholdMember
from app.domains.households.repository import HouseholdRepository
from app.domains.recurring.models import RecurringExpense
from app.domains.recurring.repository import RecurringExpenseRepository

DEFAULT_RULE_NAME = "Répartition par défaut"
HUNDRED = Decimal("100.000")


def _target_percentages(
    members: list[HouseholdMember],
) -> dict[uuid.UUID, Decimal]:
    if len(members) == 1:
        return {members[0].user_id: HUNDRED}
    if len(members) == 2:
        return {
            members[0].user_id: Decimal("55.000"),
            members[1].user_id: Decimal("45.000"),
        }

    share = (Decimal("100") / len(members)).quantize(Decimal("0.001"))
    percentages = {member.user_id: share for member in members}
    remainder = HUNDRED - sum(percentages.values(), Decimal("0"))
    percentages[members[-1].user_id] += remainder
    return percentages


def _replace_members(
    rule: AllocationRule,
    percentages: dict[uuid.UUID, Decimal],
) -> None:
    existing = {member.user_id: member for member in rule.members}
    for user_id, percentage in percentages.items():
        member = existing.pop(user_id, None)
        if member is None:
            rule.members.append(
                AllocationRuleMember(
                    user_id=user_id,
                    percentage=percentage,
                )
            )
        else:
            member.percentage = percentage
    for member in existing.values():
        rule.members.remove(member)


def ensure_default_allocation_rule(
    db: Session,
    household_id: uuid.UUID,
) -> AllocationRule | None:
    """Crée ou adapte la règle par défaut sans commit."""
    household_repository = HouseholdRepository(db)
    allocation_repository = AllocationRepository(db)
    members = [
        member for member in household_repository.list_members(household_id) if member.is_active
    ]
    if not members:
        return None

    target = _target_percentages(members)
    rule = allocation_repository.get_default_rule(household_id)
    if rule is None:
        rule = AllocationRule(
            household_id=household_id,
            name=DEFAULT_RULE_NAME,
            is_default=True,
        )
        _replace_members(rule, target)
        allocation_repository.add_rule(rule)
        db.flush()
        return rule

    if not rule.members:
        _replace_members(rule, target)
        db.flush()
    elif len(rule.members) == 1 and len(members) == 2:
        # Passage du foyer à un membre à deux membres : 100 % devient 55/45.
        _replace_members(rule, target)
        db.flush()
    return rule


class AllocationService:
    def __init__(
        self,
        db: Session,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._db = db
        self._now = now or utcnow
        self._allocations = AllocationRepository(db)
        self._households = HouseholdRepository(db)
        self._recurring = RecurringExpenseRepository(db)
        self._audit = AuditRepository(db)

    def list_rules(self, membership: HouseholdMember) -> list[AllocationRule]:
        ensure_default_allocation_rule(self._db, membership.household_id)
        self._db.commit()
        return self._allocations.list_rules(membership.household_id)

    def set_default_rule(
        self,
        membership: HouseholdMember,
        members: list[AllocationMemberInput],
    ) -> AllocationRule:
        self._require_owner(membership)
        percentages = self._validate_members(membership.household_id, members)
        rule = ensure_default_allocation_rule(self._db, membership.household_id)
        if rule is None:
            raise AppError(
                code="no_household_members",
                message="Aucun membre actif dans le foyer.",
                status_code=409,
            )
        _replace_members(rule, percentages)
        self._db.flush()

        self._audit.add(
            occurred_at=self._now(),
            action="allocation.default_updated",
            entity_type="allocation_rule",
            entity_id=rule.id,
            actor_user_id=membership.user_id,
            household_id=membership.household_id,
            request_id=request_id_var.get(),
        )
        self._db.commit()
        return rule

    def set_recurring_rule(
        self,
        membership: HouseholdMember,
        recurring_id: uuid.UUID,
        members: list[AllocationMemberInput],
    ) -> AllocationRule:
        self._require_owner(membership)
        recurring = self._shared_recurring(membership, recurring_id)
        percentages = self._validate_members(membership.household_id, members)

        rule: AllocationRule | None = None
        if recurring.allocation_rule_id is not None:
            rule = self._allocations.get_rule(recurring.allocation_rule_id)
        if rule is None or rule.is_default:
            rule = AllocationRule(
                household_id=membership.household_id,
                name=f"Répartition {recurring.label}",
                is_default=False,
            )
            _replace_members(rule, percentages)
            self._allocations.add_rule(rule)
            self._db.flush()
            recurring.allocation_rule_id = rule.id
        else:
            _replace_members(rule, percentages)
            self._db.flush()

        self._audit.add(
            occurred_at=self._now(),
            action="allocation.recurring_updated",
            entity_type="allocation_rule",
            entity_id=rule.id,
            actor_user_id=membership.user_id,
            household_id=membership.household_id,
            request_id=request_id_var.get(),
        )
        self._db.commit()
        return rule

    def clear_recurring_rule(
        self,
        membership: HouseholdMember,
        recurring_id: uuid.UUID,
    ) -> RecurringExpense:
        self._require_owner(membership)
        recurring = self._shared_recurring(membership, recurring_id)
        recurring.allocation_rule_id = None
        self._audit.add(
            occurred_at=self._now(),
            action="allocation.recurring_cleared",
            entity_type="recurring_expense",
            entity_id=recurring.id,
            actor_user_id=membership.user_id,
            household_id=membership.household_id,
            request_id=request_id_var.get(),
        )
        self._db.commit()
        return recurring

    def resolve_rule(
        self,
        recurring: RecurringExpense,
        default_rule: AllocationRule,
    ) -> AllocationRule:
        if recurring.allocation_rule_id is not None:
            rule = self._allocations.get_rule(recurring.allocation_rule_id)
            if rule is not None and rule.members:
                return rule
        return default_rule

    def _validate_members(
        self,
        household_id: uuid.UUID,
        members: list[AllocationMemberInput],
    ) -> dict[uuid.UUID, Decimal]:
        active_members = [
            member for member in self._households.list_members(household_id) if member.is_active
        ]
        active_ids = {member.user_id for member in active_members}
        input_ids = [member.user_id for member in members]
        if len(input_ids) != len(set(input_ids)):
            raise AppError(
                code="invalid_allocation",
                message="Un membre est présent plusieurs fois.",
                status_code=422,
            )
        if set(input_ids) != active_ids:
            raise AppError(
                code="invalid_allocation",
                message="La répartition doit couvrir exactement les membres actifs du foyer.",
                status_code=422,
            )

        percentages = {member.user_id: member.percentage for member in members}
        total = sum(percentages.values(), Decimal("0")).quantize(Decimal("0.001"))
        if total != HUNDRED:
            raise AppError(
                code="invalid_allocation",
                message="La somme des pourcentages doit être égale à 100 %.",
                status_code=422,
            )
        return percentages

    def _shared_recurring(
        self,
        membership: HouseholdMember,
        recurring_id: uuid.UUID,
    ) -> RecurringExpense:
        recurring = self._recurring.get_by_id(recurring_id)
        if recurring is None or recurring.scope != "shared":
            raise AppError(
                code="allocation_not_applicable",
                message="Une répartition spécifique ne s'applique qu'aux charges communes.",
                status_code=422,
            )
        if recurring.household_id != membership.household_id:
            raise AppError(
                code="not_found",
                message="Charge récurrente introuvable.",
                status_code=404,
            )
        return recurring

    @staticmethod
    def _require_owner(membership: HouseholdMember) -> None:
        if membership.role != "owner":
            raise AppError(
                code="forbidden",
                message="Seul le propriétaire du foyer peut modifier les répartitions.",
                status_code=403,
            )
