import uuid
from collections.abc import Callable
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.core.errors import AppError
from app.core.periods import add_months, current_period, parse_period
from app.core.request_context import request_id_var
from app.domains.audit.repository import AuditRepository
from app.domains.categories.access import get_usable_category
from app.domains.households.models import HouseholdMember
from app.domains.recurring.models import RecurringExpense, RecurringOccurrence
from app.domains.recurring.repository import (
    RecurringExpenseRepository,
    RecurringOccurrenceRepository,
)
from app.domains.recurring.schemas import (
    RecurringExpenseCreate,
    RecurringExpenseUpdate,
    RecurringOccurrenceConfirmAmount,
    RecurringOccurrenceCorrectPayment,
    RecurringOccurrenceMarkPaid,
    RecurringOccurrenceSkip,
)
from app.domains.transactions.repository import TransactionRepository
from app.domains.transactions.schemas import TransactionCreate
from app.domains.transactions.service import TransactionService
from app.domains.users.models import User

FREQUENCY_MONTHS = {
    "monthly": 1,
    "quarterly": 3,
    "semiannual": 6,
    "yearly": 12,
}


class RecurringService:
    def __init__(
        self,
        db: Session,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._db = db
        self._now = now or utcnow
        self._recurring = RecurringExpenseRepository(db)
        self._occurrences = RecurringOccurrenceRepository(db)
        self._transactions = TransactionRepository(db)
        self._audit = AuditRepository(db)

    def create(
        self,
        membership: HouseholdMember,
        user: User,
        payload: RecurringExpenseCreate,
    ) -> RecurringExpense:
        get_usable_category(self._db, membership.household_id, payload.category_id)
        self._validate_definition(
            amount_cents=payload.amount_cents,
            amount_is_variable=payload.amount_is_variable,
            start_date=payload.start_date,
            end_date=payload.end_date,
        )
        recurring = RecurringExpense(
            household_id=(membership.household_id if payload.scope == "shared" else None),
            owner_user_id=user.id,
            category_id=payload.category_id,
            label=payload.label,
            amount_cents=payload.amount_cents,
            scope=payload.scope,
            frequency=payload.frequency,
            start_date=payload.start_date,
            end_date=payload.end_date,
            due_day=payload.due_day,
            amount_is_variable=payload.amount_is_variable,
            is_active=True,
        )
        self._recurring.add(recurring)
        self._db.flush()

        self._audit.add(
            occurred_at=self._now(),
            action="recurring.created",
            entity_type="recurring_expense",
            entity_id=recurring.id,
            actor_user_id=user.id,
            household_id=recurring.household_id,
            request_id=request_id_var.get(),
        )
        self._db.commit()
        return recurring

    def list_recurring(
        self,
        membership: HouseholdMember,
        user: User,
        *,
        scope: str | None,
        is_active: bool | None,
        category_id: uuid.UUID | None,
        limit: int,
        offset: int,
    ) -> tuple[list[RecurringExpense], int]:
        return self._recurring.list_for_member(
            user_id=user.id,
            household_id=membership.household_id,
            scope=scope,
            is_active=is_active,
            category_id=category_id,
            limit=limit,
            offset=offset,
        )

    def get(
        self,
        membership: HouseholdMember,
        user: User,
        recurring_id: uuid.UUID,
    ) -> RecurringExpense:
        recurring = self._recurring.get_by_id(recurring_id)
        if recurring is None:
            raise self._not_found()
        self._assert_access(membership, user, recurring)
        return recurring

    def update(
        self,
        membership: HouseholdMember,
        user: User,
        recurring_id: uuid.UUID,
        payload: RecurringExpenseUpdate,
    ) -> RecurringExpense:
        recurring = self.get(membership, user, recurring_id)

        if payload.category_id is not None:
            get_usable_category(
                self._db,
                membership.household_id,
                payload.category_id,
            )
            recurring.category_id = payload.category_id
        if payload.label is not None:
            recurring.label = payload.label
        if payload.amount_cents is not None:
            recurring.amount_cents = payload.amount_cents
        if payload.frequency is not None:
            recurring.frequency = payload.frequency
        if payload.start_date is not None:
            recurring.start_date = payload.start_date
        if "end_date" in payload.model_fields_set:
            recurring.end_date = payload.end_date
        if "due_day" in payload.model_fields_set:
            recurring.due_day = payload.due_day
        if payload.amount_is_variable is not None:
            recurring.amount_is_variable = payload.amount_is_variable

        self._validate_definition(
            amount_cents=recurring.amount_cents,
            amount_is_variable=recurring.amount_is_variable,
            start_date=recurring.start_date,
            end_date=recurring.end_date,
        )
        self._audit.add(
            occurred_at=self._now(),
            action="recurring.updated",
            entity_type="recurring_expense",
            entity_id=recurring.id,
            actor_user_id=user.id,
            household_id=recurring.household_id,
            details={"fields": sorted(payload.model_fields_set)},
            request_id=request_id_var.get(),
        )
        self._db.commit()
        return recurring

    def deactivate(
        self,
        membership: HouseholdMember,
        user: User,
        recurring_id: uuid.UUID,
    ) -> RecurringExpense:
        recurring = self.get(membership, user, recurring_id)
        if recurring.is_active:
            recurring.is_active = False
            self._audit.add(
                occurred_at=self._now(),
                action="recurring.deactivated",
                entity_type="recurring_expense",
                entity_id=recurring.id,
                actor_user_id=user.id,
                household_id=recurring.household_id,
                request_id=request_id_var.get(),
            )
            self._db.commit()
        return recurring

    def list_occurrences(
        self,
        membership: HouseholdMember,
        user: User,
        recurring_id: uuid.UUID,
        *,
        period: str | None,
        status: str | None,
    ) -> list[RecurringOccurrence]:
        recurring = self.get(membership, user, recurring_id)
        period_value = period or current_period(membership.household.timezone)
        start, end = parse_period(period_value)

        if recurring.is_active and self._generate_for([recurring], start, end):
            self._db.commit()

        return self._occurrences.list_for_recurring(
            recurring.id,
            start=start,
            end=end,
            status=status,
        )

    def ensure_occurrences_for_period(
        self,
        membership: HouseholdMember,
        user: User,
        period: str | None,
        *,
        commit: bool = True,
    ) -> int:
        """Génère les échéances manquantes des récurrences accessibles au membre."""
        period_value = period or current_period(membership.household.timezone)
        start, end = parse_period(period_value)
        recurrings = self._recurring.list_active_for_member(
            user.id,
            membership.household_id,
        )
        generated = self._generate_for(recurrings, start, end)
        if generated and commit:
            self._db.commit()
        return generated

    def ensure_shared_occurrences_for_period(
        self,
        household_id: uuid.UUID,
        period: str | None,
        *,
        commit: bool = False,
    ) -> int:
        """Génère les échéances manquantes des récurrences communes du foyer."""
        period_value = period or current_period()
        start, end = parse_period(period_value)
        generated = self._generate_for(
            self._recurring.list_active_shared(household_id),
            start,
            end,
        )
        if generated and commit:
            self._db.commit()
        return generated

    def generate_all_for_period(
        self,
        period: str | None = None,
        *,
        commit: bool = True,
    ) -> int:
        """Génère les échéances manquantes de toutes les récurrences actives."""
        period_value = period or current_period()
        start, end = parse_period(period_value)
        generated = self._generate_for(
            self._recurring.list_all_active(),
            start,
            end,
        )
        if generated and commit:
            self._db.commit()
        return generated

    def mark_occurrence_paid(
        self,
        membership: HouseholdMember,
        user: User,
        occurrence_id: uuid.UUID,
        payload: RecurringOccurrenceMarkPaid,
    ) -> RecurringOccurrence:
        occurrence = self._occurrences.get_for_update(occurrence_id)
        if occurrence is None:
            raise self._occurrence_not_found()

        recurring = self._recurring.get_by_id(occurrence.recurring_expense_id)
        if recurring is None:
            raise self._occurrence_not_found()
        self._assert_access(membership, user, recurring)

        if occurrence.status == "paid":
            return occurrence
        if occurrence.status == "skipped":
            raise AppError(
                code="occurrence_skipped",
                message="Une échéance ignorée ne peut pas être pointée payée.",
                status_code=409,
            )

        default_amount = (
            occurrence.confirmed_amount_cents
            or occurrence.expected_amount_cents
            or recurring.amount_cents
        )
        if payload.payment_amount_cents is None:
            if default_amount is None or (
                recurring.amount_is_variable and occurrence.confirmed_amount_cents is None
            ):
                raise AppError(
                    code="payment_amount_required",
                    message="Le montant réel est obligatoire pour une charge variable.",
                    status_code=422,
                )
            amount_cents = default_amount
        else:
            amount_cents = payload.payment_amount_cents

        paid_local = payload.paid_at.astimezone(ZoneInfo(membership.household.timezone))
        transaction = TransactionService(self._db, self._now).create(
            membership,
            user,
            TransactionCreate(
                label=recurring.label,
                amount_cents=amount_cents,
                transaction_date=paid_local.date(),
                category_id=recurring.category_id,
                scope=recurring.scope,
                transaction_type="expense",
                paid_at=payload.paid_at,
                notes=payload.note,
            ),
            recurring_occurrence_id=occurrence.id,
            commit=False,
            allow_inactive_category=True,
        )

        occurrence.status = "paid"
        occurrence.paid_at = payload.paid_at
        occurrence.payment_amount_cents = amount_cents
        occurrence.payment_note = payload.note
        occurrence.transaction_id = transaction.id

        self._audit.add(
            occurred_at=self._now(),
            action="recurring_occurrence.paid",
            entity_type="recurring_occurrence",
            entity_id=occurrence.id,
            actor_user_id=user.id,
            household_id=recurring.household_id,
            details={
                "amount_cents": amount_cents,
                "paid_at": payload.paid_at.isoformat(),
            },
            request_id=request_id_var.get(),
        )
        self._db.commit()
        return occurrence

    def confirm_amount(
        self,
        membership: HouseholdMember,
        user: User,
        occurrence_id: uuid.UUID,
        payload: RecurringOccurrenceConfirmAmount,
    ) -> RecurringOccurrence:
        occurrence, recurring = self._locked_occurrence(membership, user, occurrence_id)
        if occurrence.status == "paid":
            raise AppError(
                code="occurrence_paid",
                message="Une échéance payée doit être corrigée explicitement.",
                status_code=409,
            )
        if occurrence.status == "skipped":
            raise AppError(
                code="occurrence_skipped",
                message="Une échéance ignorée ne peut pas être confirmée.",
                status_code=409,
            )

        occurrence.confirmed_amount_cents = payload.confirmed_amount_cents
        occurrence.confirmed_at = self._now()
        occurrence.status = "confirmed"

        self._audit.add(
            occurred_at=self._now(),
            action="recurring_occurrence.confirmed",
            entity_type="recurring_occurrence",
            entity_id=occurrence.id,
            actor_user_id=user.id,
            household_id=recurring.household_id,
            details={"amount_cents": payload.confirmed_amount_cents},
            request_id=request_id_var.get(),
        )
        self._db.commit()
        return occurrence

    def skip_occurrence(
        self,
        membership: HouseholdMember,
        user: User,
        occurrence_id: uuid.UUID,
        payload: RecurringOccurrenceSkip,
    ) -> RecurringOccurrence:
        occurrence, recurring = self._locked_occurrence(membership, user, occurrence_id)
        if occurrence.status == "paid":
            raise AppError(
                code="occurrence_paid",
                message="Une échéance payée ne peut pas être ignorée sans correction préalable.",
                status_code=409,
            )
        if occurrence.status == "skipped":
            return occurrence

        occurrence.status = "skipped"
        occurrence.skipped_at = self._now()
        occurrence.skip_reason = payload.reason

        self._audit.add(
            occurred_at=self._now(),
            action="recurring_occurrence.skipped",
            entity_type="recurring_occurrence",
            entity_id=occurrence.id,
            actor_user_id=user.id,
            household_id=recurring.household_id,
            details={"reason": payload.reason},
            request_id=request_id_var.get(),
        )
        self._db.commit()
        return occurrence

    def correct_payment(
        self,
        membership: HouseholdMember,
        user: User,
        occurrence_id: uuid.UUID,
        payload: RecurringOccurrenceCorrectPayment,
    ) -> RecurringOccurrence:
        occurrence, recurring = self._locked_occurrence(membership, user, occurrence_id)
        if occurrence.status != "paid" or occurrence.transaction_id is None:
            raise AppError(
                code="occurrence_not_paid",
                message="Seule une échéance payée peut être corrigée.",
                status_code=409,
            )

        transaction = self._transactions.get_by_id(occurrence.transaction_id)
        if transaction is None or transaction.deleted_at is not None:
            raise AppError(
                code="linked_transaction_missing",
                message="La transaction liée à cette échéance est introuvable.",
                status_code=409,
            )
        refunded = self._transactions.sum_refunds(transaction.id)
        if payload.payment_amount_cents < refunded:
            raise AppError(
                code="invalid_payment_amount",
                message="Le montant corrigé ne peut pas être inférieur aux remboursements.",
                status_code=422,
            )

        previous_amount = occurrence.payment_amount_cents
        previous_paid_at = occurrence.paid_at
        paid_local = payload.paid_at.astimezone(ZoneInfo(membership.household.timezone))

        transaction.amount_cents = payload.payment_amount_cents
        transaction.transaction_date = paid_local.date()
        transaction.paid_at = payload.paid_at
        if payload.note is not None:
            transaction.notes = payload.note

        occurrence.payment_amount_cents = payload.payment_amount_cents
        occurrence.paid_at = payload.paid_at
        occurrence.payment_note = payload.note

        self._audit.add(
            occurred_at=self._now(),
            action="recurring_occurrence.payment_corrected",
            entity_type="recurring_occurrence",
            entity_id=occurrence.id,
            actor_user_id=user.id,
            household_id=recurring.household_id,
            details={
                "previous_amount_cents": previous_amount,
                "amount_cents": payload.payment_amount_cents,
                "previous_paid_at": (
                    previous_paid_at.isoformat() if previous_paid_at is not None else None
                ),
                "paid_at": payload.paid_at.isoformat(),
            },
            request_id=request_id_var.get(),
        )
        self._db.commit()
        return occurrence

    def _locked_occurrence(
        self,
        membership: HouseholdMember,
        user: User,
        occurrence_id: uuid.UUID,
    ) -> tuple[RecurringOccurrence, RecurringExpense]:
        occurrence = self._occurrences.get_for_update(occurrence_id)
        if occurrence is None:
            raise self._occurrence_not_found()
        recurring = self._recurring.get_by_id(occurrence.recurring_expense_id)
        if recurring is None:
            raise self._occurrence_not_found()
        self._assert_access(membership, user, recurring)
        return occurrence, recurring

    def _generate_for(
        self,
        recurrings: list[RecurringExpense],
        start: date,
        end: date,
    ) -> int:
        rows = [
            {
                "recurring_expense_id": recurring.id,
                "due_date": due_date,
                "expected_amount_cents": recurring.amount_cents,
                "status": "pending",
            }
            for recurring in recurrings
            for due_date in self._due_dates(recurring, start, end)
        ]
        return self._occurrences.insert_missing(rows)

    @staticmethod
    def _due_dates(
        recurring: RecurringExpense,
        start: date,
        end: date,
    ) -> list[date]:
        if recurring.start_date > end:
            return []
        if recurring.end_date is not None and recurring.end_date < start:
            return []

        if recurring.frequency == "weekly":
            first = recurring.start_date
            if first < start:
                days = (start - first).days
                first += timedelta(days=7 * ((days + 6) // 7))

            dates: list[date] = []
            while first <= end:
                if recurring.end_date is not None and first > recurring.end_date:
                    break
                dates.append(first)
                first += timedelta(days=7)
            return dates

        interval = FREQUENCY_MONTHS[recurring.frequency]
        day = recurring.due_day or recurring.start_date.day
        base_month = recurring.start_date.replace(day=1)
        period_month = start.replace(day=1)
        month_diff = (period_month.year - base_month.year) * 12 + (
            period_month.month - base_month.month
        )
        index = max(0, month_diff // interval)
        candidate = add_months(base_month, index * interval, day)
        while candidate < start:
            index += 1
            candidate = add_months(base_month, index * interval, day)

        dates = []
        while candidate <= end:
            if recurring.end_date is not None and candidate > recurring.end_date:
                break
            if candidate >= recurring.start_date:
                dates.append(candidate)
            index += 1
            candidate = add_months(base_month, index * interval, day)
        return dates

    @staticmethod
    def _validate_definition(
        *,
        amount_cents: int | None,
        amount_is_variable: bool,
        start_date: date,
        end_date: date | None,
    ) -> None:
        if not amount_is_variable and amount_cents is None:
            raise AppError(
                code="invalid_recurring_amount",
                message="Un montant est obligatoire pour une charge fixe.",
                status_code=422,
            )
        if end_date is not None and end_date < start_date:
            raise AppError(
                code="invalid_recurring_dates",
                message="La date de fin doit être postérieure à la date de début.",
                status_code=422,
            )

    @staticmethod
    def _assert_access(
        membership: HouseholdMember,
        user: User,
        recurring: RecurringExpense,
    ) -> None:
        if recurring.scope == "personal" and recurring.owner_user_id != user.id:
            raise AppError(
                code="not_found",
                message="Charge récurrente introuvable.",
                status_code=404,
            )
        if recurring.scope == "shared" and recurring.household_id != membership.household_id:
            raise AppError(
                code="not_found",
                message="Charge récurrente introuvable.",
                status_code=404,
            )

    @staticmethod
    def _not_found() -> AppError:
        return AppError(
            code="not_found",
            message="Charge récurrente introuvable.",
            status_code=404,
        )

    @staticmethod
    def _occurrence_not_found() -> AppError:
        return AppError(
            code="not_found",
            message="Échéance introuvable.",
            status_code=404,
        )
