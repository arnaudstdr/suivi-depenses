import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.domains.allocations.models import (
    AllocationRule,
    AllocationRuleMember,
    HouseholdContribution,
)


class AllocationRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_default_rule(self, household_id: uuid.UUID) -> AllocationRule | None:
        return self._db.scalar(
            select(AllocationRule)
            .options(selectinload(AllocationRule.members).joinedload(AllocationRuleMember.user))
            .where(
                AllocationRule.household_id == household_id,
                AllocationRule.is_default.is_(True),
            )
        )

    def get_rule(self, rule_id: uuid.UUID) -> AllocationRule | None:
        return self._db.scalar(
            select(AllocationRule)
            .options(selectinload(AllocationRule.members).joinedload(AllocationRuleMember.user))
            .where(AllocationRule.id == rule_id)
        )

    def list_rules(self, household_id: uuid.UUID) -> list[AllocationRule]:
        return list(
            self._db.scalars(
                select(AllocationRule)
                .options(selectinload(AllocationRule.members).joinedload(AllocationRuleMember.user))
                .where(AllocationRule.household_id == household_id)
                .order_by(AllocationRule.is_default.desc(), AllocationRule.name)
            ).all()
        )

    def add_rule(self, rule: AllocationRule) -> AllocationRule:
        self._db.add(rule)
        return rule

    def get_contribution(
        self,
        household_id: uuid.UUID,
        user_id: uuid.UUID,
        period_start: date,
    ) -> HouseholdContribution | None:
        return self._db.scalar(
            select(HouseholdContribution).where(
                HouseholdContribution.household_id == household_id,
                HouseholdContribution.user_id == user_id,
                HouseholdContribution.period_start == period_start,
            )
        )

    def get_contribution_for_update(
        self,
        contribution_id: uuid.UUID,
    ) -> HouseholdContribution | None:
        return self._db.scalar(
            select(HouseholdContribution)
            .where(HouseholdContribution.id == contribution_id)
            .with_for_update()
        )

    def list_contributions(
        self,
        household_id: uuid.UUID,
        period_start: date,
    ) -> list[HouseholdContribution]:
        return list(
            self._db.scalars(
                select(HouseholdContribution)
                .options(joinedload(HouseholdContribution.user))
                .where(
                    HouseholdContribution.household_id == household_id,
                    HouseholdContribution.period_start == period_start,
                )
                .order_by(HouseholdContribution.created_at)
            ).all()
        )

    def add_contribution(
        self,
        contribution: HouseholdContribution,
    ) -> HouseholdContribution:
        self._db.add(contribution)
        return contribution
