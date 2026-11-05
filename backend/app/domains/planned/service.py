import uuid
from collections.abc import Callable
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.core.errors import AppError
from app.core.request_context import request_id_var
from app.domains.audit.repository import AuditRepository
from app.domains.categories.access import get_usable_category
from app.domains.households.models import HouseholdMember
from app.domains.planned.models import PlannedExpense
from app.domains.planned.repository import PlannedExpenseRepository
from app.domains.planned.schemas import (
    PlannedExpenseCreate,
    PlannedExpenseMarkPaid,
    PlannedExpenseUpdate,
)
from app.domains.transactions.schemas import TransactionCreate
from app.domains.transactions.service import TransactionService
from app.domains.users.models import User


class PlannedExpenseService:
    def __init__(
        self,
        db: Session,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._db = db
        self._now = now or utcnow
        self._planned = PlannedExpenseRepository(db)
        self._audit = AuditRepository(db)

    def create(
        self,
        membership: HouseholdMember,
        user: User,
        payload: PlannedExpenseCreate,
    ) -> PlannedExpense:
        get_usable_category(
            self._db,
            membership.household_id,
            payload.category_id,
        )
        planned = PlannedExpense(
            household_id=(membership.household_id if payload.scope == "shared" else None),
            user_id=user.id,
            category_id=payload.category_id,
            label=payload.label,
            amount_cents=payload.amount_cents,
            scope=payload.scope,
            planned_date=payload.planned_date,
            status=payload.status,
        )
        self._planned.add(planned)
        self._db.flush()

        self._audit.add(
            occurred_at=self._now(),
            action="planned.created",
            entity_type="planned_expense",
            entity_id=planned.id,
            actor_user_id=user.id,
            household_id=planned.household_id,
            details={"scope": planned.scope, "status": planned.status},
            request_id=request_id_var.get(),
        )
        self._db.commit()
        return planned

    def get(
        self,
        membership: HouseholdMember,
        user: User,
        planned_id: uuid.UUID,
    ) -> PlannedExpense:
        return self._accessible(membership, user, planned_id)

    def list(
        self,
        membership: HouseholdMember,
        user: User,
        *,
        scope: str | None,
        status: str | None,
        category_id: uuid.UUID | None,
        date_from: date | None,
        date_to: date | None,
        limit: int,
        offset: int,
    ) -> tuple[list[PlannedExpense], int]:
        return self._planned.list_for_member(
            user_id=user.id,
            household_id=membership.household_id,
            scope=scope,
            status=status,
            category_id=category_id,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            offset=offset,
        )

    def update(
        self,
        membership: HouseholdMember,
        user: User,
        planned_id: uuid.UUID,
        payload: PlannedExpenseUpdate,
    ) -> PlannedExpense:
        planned = self._accessible(membership, user, planned_id)
        if planned.status in {"paid", "cancelled"}:
            raise AppError(
                code="planned_not_editable",
                message="Une dépense payée ou annulée ne peut plus être modifiée.",
                status_code=409,
            )

        if payload.category_id is not None:
            get_usable_category(
                self._db,
                membership.household_id,
                payload.category_id,
            )
            planned.category_id = payload.category_id
        if payload.label is not None:
            planned.label = payload.label
        if payload.amount_cents is not None:
            planned.amount_cents = payload.amount_cents
        if payload.planned_date is not None:
            planned.planned_date = payload.planned_date
        if payload.status is not None:
            planned.status = payload.status

        self._audit.add(
            occurred_at=self._now(),
            action="planned.updated",
            entity_type="planned_expense",
            entity_id=planned.id,
            actor_user_id=user.id,
            household_id=planned.household_id,
            details={"fields": sorted(payload.model_fields_set)},
            request_id=request_id_var.get(),
        )
        self._db.commit()
        return planned

    def mark_paid(
        self,
        membership: HouseholdMember,
        user: User,
        planned_id: uuid.UUID,
        payload: PlannedExpenseMarkPaid,
    ) -> PlannedExpense:
        planned = self._planned.get_for_update(planned_id)
        if planned is None:
            raise self._not_found()
        self._assert_access(membership, user, planned)

        if planned.status == "paid":
            return planned
        if planned.status == "cancelled":
            raise AppError(
                code="planned_cancelled",
                message="Une dépense annulée ne peut pas être payée.",
                status_code=409,
            )

        paid_local = payload.paid_at.astimezone(ZoneInfo(membership.household.timezone))
        amount_cents = payload.payment_amount_cents or planned.amount_cents
        transaction = TransactionService(self._db, self._now).create(
            membership,
            user,
            TransactionCreate(
                label=planned.label,
                amount_cents=amount_cents,
                transaction_date=paid_local.date(),
                category_id=planned.category_id,
                scope=planned.scope,
                transaction_type="expense",
                paid_at=payload.paid_at,
                notes=payload.note,
            ),
            commit=False,
            allow_inactive_category=True,
        )

        planned.status = "paid"
        planned.transaction_id = transaction.id
        self._audit.add(
            occurred_at=self._now(),
            action="planned.paid",
            entity_type="planned_expense",
            entity_id=planned.id,
            actor_user_id=user.id,
            household_id=planned.household_id,
            request_id=request_id_var.get(),
        )
        self._db.commit()
        return planned

    def cancel(
        self,
        membership: HouseholdMember,
        user: User,
        planned_id: uuid.UUID,
    ) -> PlannedExpense:
        planned = self._accessible(membership, user, planned_id)
        if planned.status == "paid":
            raise AppError(
                code="planned_paid",
                message="Une dépense payée ne peut pas être annulée.",
                status_code=409,
            )
        if planned.status == "cancelled":
            return planned

        planned.status = "cancelled"
        self._audit.add(
            occurred_at=self._now(),
            action="planned.cancelled",
            entity_type="planned_expense",
            entity_id=planned.id,
            actor_user_id=user.id,
            household_id=planned.household_id,
            request_id=request_id_var.get(),
        )
        self._db.commit()
        return planned

    def _accessible(
        self,
        membership: HouseholdMember,
        user: User,
        planned_id: uuid.UUID,
    ) -> PlannedExpense:
        planned = self._planned.get_by_id(planned_id)
        if planned is None:
            raise self._not_found()
        self._assert_access(membership, user, planned)
        return planned

    @staticmethod
    def _assert_access(
        membership: HouseholdMember,
        user: User,
        planned: PlannedExpense,
    ) -> None:
        if planned.scope == "personal" and planned.user_id != user.id:
            raise AppError(
                code="not_found",
                message="Dépense prévue introuvable.",
                status_code=404,
            )
        if planned.scope == "shared" and planned.household_id != membership.household_id:
            raise AppError(
                code="not_found",
                message="Dépense prévue introuvable.",
                status_code=404,
            )

    @staticmethod
    def _not_found() -> AppError:
        return AppError(
            code="not_found",
            message="Dépense prévue introuvable.",
            status_code=404,
        )
