import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.domains.households.models import Household, HouseholdMember


class HouseholdRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_first(self) -> Household | None:
        return self._db.scalar(select(Household).order_by(Household.created_at).limit(1))

    def get_for_update(self, household_id: uuid.UUID) -> Household | None:
        return self._db.scalar(
            select(Household).where(Household.id == household_id).with_for_update()
        )

    def add(self, household: Household) -> Household:
        self._db.add(household)
        return household

    def count_active_members(self, household_id: uuid.UUID) -> int:
        count = self._db.scalar(
            select(func.count())
            .select_from(HouseholdMember)
            .where(
                HouseholdMember.household_id == household_id,
                HouseholdMember.is_active.is_(True),
            )
        )
        return int(count or 0)

    def get_membership(self, user_id: uuid.UUID) -> HouseholdMember | None:
        return self._db.scalar(
            select(HouseholdMember)
            .options(joinedload(HouseholdMember.household))
            .where(
                HouseholdMember.user_id == user_id,
                HouseholdMember.is_active.is_(True),
            )
        )

    def list_members(self, household_id: uuid.UUID) -> list[HouseholdMember]:
        return list(
            self._db.scalars(
                select(HouseholdMember)
                .options(joinedload(HouseholdMember.user))
                .where(HouseholdMember.household_id == household_id)
                .order_by(HouseholdMember.created_at)
            ).all()
        )

    def add_member(self, member: HouseholdMember) -> HouseholdMember:
        self._db.add(member)
        return member
