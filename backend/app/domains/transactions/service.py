import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.core.errors import AppError
from app.core.periods import current_period, parse_period
from app.core.request_context import request_id_var
from app.domains.audit.repository import AuditRepository
from app.domains.budgets.service import ensure_grocery_budget
from app.domains.categories.access import get_usable_category
from app.domains.categories.models import Category
from app.domains.households.models import HouseholdMember
from app.domains.transactions.models import Transaction
from app.domains.transactions.repository import TransactionRepository
from app.domains.transactions.schemas import TransactionCreate, TransactionUpdate
from app.domains.users.models import User


def default_paid_at(transaction_date: date, timezone: str) -> datetime:
    local_noon = datetime.combine(
        transaction_date,
        time(hour=12),
        tzinfo=ZoneInfo(timezone),
    )
    return local_noon.astimezone(UTC)


class TransactionService:
    def __init__(
        self,
        db: Session,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._db = db
        self._now = now or utcnow
        self._transactions = TransactionRepository(db)
        self._audit = AuditRepository(db)

    def create(
        self,
        membership: HouseholdMember,
        user: User,
        payload: TransactionCreate,
        *,
        recurring_occurrence_id: uuid.UUID | None = None,
        commit: bool = True,
        allow_inactive_category: bool = False,
    ) -> Transaction:
        if payload.transaction_type == "refund":
            if payload.original_transaction_id is None:
                raise self._invalid_refund()
            original = self._accessible_transaction(
                membership,
                user,
                payload.original_transaction_id,
            )
            if original.transaction_type != "expense":
                raise self._invalid_refund()
            if original.scope != payload.scope:
                raise self._invalid_refund()
            if original.category_id != payload.category_id:
                raise self._invalid_refund("Le remboursement doit utiliser la catégorie d'origine.")
            if payload.budget_id is not None and payload.budget_id != original.budget_id:
                raise self._invalid_budget()
            refunded = self._transactions.sum_refunds(original.id)
            if payload.amount_cents > original.amount_cents - refunded:
                raise self._invalid_refund(
                    "Le remboursement dépasse le montant encore remboursable."
                )
            household_id = original.household_id
            budget_id = original.budget_id
            category_id = original.category_id
        else:
            category = self._usable_category(
                membership,
                payload.category_id,
                require_active=not allow_inactive_category,
            )
            category_id = category.id

            if payload.scope == "personal":
                if payload.budget_id is not None:
                    raise self._invalid_budget()
                household_id = None
                budget_id = None
            else:
                household_id = membership.household_id
                if category.is_grocery:
                    grocery_budget = ensure_grocery_budget(
                        self._db,
                        membership.household_id,
                    )
                    if payload.budget_id is not None and payload.budget_id != grocery_budget.id:
                        raise self._invalid_budget()
                    budget_id = grocery_budget.id
                else:
                    if payload.budget_id is not None:
                        raise self._invalid_budget()
                    budget_id = None

        paid_at = payload.paid_at or default_paid_at(
            payload.transaction_date,
            membership.household.timezone,
        )
        transaction = Transaction(
            household_id=household_id,
            user_id=user.id,
            category_id=category_id,
            label=payload.label,
            amount_cents=payload.amount_cents,
            transaction_type=payload.transaction_type,
            scope=payload.scope,
            budget_id=budget_id,
            transaction_date=payload.transaction_date,
            paid_at=paid_at,
            status="paid",
            original_transaction_id=payload.original_transaction_id,
            recurring_occurrence_id=recurring_occurrence_id,
            notes=payload.notes,
        )
        self._transactions.add(transaction)
        self._db.flush()

        self._audit.add(
            occurred_at=self._now(),
            action="transaction.created",
            entity_type="transaction",
            entity_id=transaction.id,
            actor_user_id=user.id,
            household_id=household_id,
            details={"scope": payload.scope, "type": payload.transaction_type},
            request_id=request_id_var.get(),
        )
        if commit:
            self._db.commit()
        return transaction

    def get(
        self,
        membership: HouseholdMember,
        user: User,
        transaction_id: uuid.UUID,
    ) -> Transaction:
        return self._accessible_transaction(membership, user, transaction_id)

    def list_transactions(
        self,
        membership: HouseholdMember,
        user: User,
        *,
        scope: str | None,
        category_id: uuid.UUID | None,
        date_from: date | None,
        date_to: date | None,
        status: str | None,
        search: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Transaction], int]:
        return self._transactions.list_for_member(
            user_id=user.id,
            household_id=membership.household_id,
            scope=scope,
            category_id=category_id,
            date_from=date_from,
            date_to=date_to,
            status=status,
            search=search,
            limit=limit,
            offset=offset,
        )

    def list_grocery(
        self,
        membership: HouseholdMember,
        *,
        period: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Transaction], int]:
        budget = ensure_grocery_budget(self._db, membership.household_id)
        self._db.commit()
        period_value = period or current_period(membership.household.timezone)
        start, end = parse_period(period_value)
        return self._transactions.list_for_budget(
            budget_id=budget.id,
            date_from=start,
            date_to=end,
            limit=limit,
            offset=offset,
        )

    def update(
        self,
        membership: HouseholdMember,
        user: User,
        transaction_id: uuid.UUID,
        payload: TransactionUpdate,
    ) -> Transaction:
        transaction = self._accessible_transaction(membership, user, transaction_id)
        self._assert_not_linked(transaction)

        if payload.category_id is not None and payload.category_id != transaction.category_id:
            if transaction.transaction_type == "refund":
                raise self._invalid_refund("La catégorie d'un remboursement est immuable.")
            category = self._usable_category(membership, payload.category_id)
            if category.is_grocery != transaction.category.is_grocery:
                raise AppError(
                    code="category_grocery_change",
                    message="Impossible de changer le caractère courses d'une transaction.",
                    status_code=422,
                )
            transaction.category_id = category.id
            if transaction.scope == "shared" and category.is_grocery:
                grocery_budget = ensure_grocery_budget(
                    self._db,
                    membership.household_id,
                )
                transaction.budget_id = grocery_budget.id
            elif transaction.scope == "shared":
                transaction.budget_id = None

        if payload.amount_cents is not None:
            self._validate_amount_change(transaction, payload.amount_cents)
            transaction.amount_cents = payload.amount_cents

        if payload.transaction_date is not None:
            transaction.transaction_date = payload.transaction_date
        if "paid_at" in payload.model_fields_set:
            if payload.paid_at is None:
                raise AppError(
                    code="invalid_paid_at",
                    message="Une transaction payée doit avoir une date de paiement.",
                    status_code=422,
                )
            transaction.paid_at = payload.paid_at
        if payload.label is not None:
            transaction.label = payload.label
        if "notes" in payload.model_fields_set:
            transaction.notes = payload.notes

        self._audit.add(
            occurred_at=self._now(),
            action="transaction.updated",
            entity_type="transaction",
            entity_id=transaction.id,
            actor_user_id=user.id,
            household_id=transaction.household_id,
            details={"fields": sorted(payload.model_fields_set)},
            request_id=request_id_var.get(),
        )
        self._db.commit()
        return transaction

    def delete(
        self,
        membership: HouseholdMember,
        user: User,
        transaction_id: uuid.UUID,
    ) -> None:
        transaction = self._accessible_transaction(membership, user, transaction_id)
        self._assert_not_linked(transaction)
        if (
            transaction.transaction_type == "expense"
            and self._transactions.sum_refunds(transaction.id) > 0
        ):
            raise AppError(
                code="transaction_has_refunds",
                message="Cette dépense possède des remboursements et ne peut pas être supprimée.",
                status_code=409,
            )

        transaction.deleted_at = self._now()
        self._audit.add(
            occurred_at=self._now(),
            action="transaction.deleted",
            entity_type="transaction",
            entity_id=transaction.id,
            actor_user_id=user.id,
            household_id=transaction.household_id,
            request_id=request_id_var.get(),
        )
        self._db.commit()

    def _accessible_transaction(
        self,
        membership: HouseholdMember,
        user: User,
        transaction_id: uuid.UUID,
    ) -> Transaction:
        transaction = self._transactions.get_by_id(transaction_id)
        if transaction is None or transaction.deleted_at is not None:
            raise self._not_found()
        if transaction.scope == "personal":
            if transaction.user_id != user.id:
                raise self._not_found()
        elif transaction.household_id != membership.household_id:
            raise self._not_found()
        return transaction

    def _usable_category(
        self,
        membership: HouseholdMember,
        category_id: uuid.UUID,
        *,
        require_active: bool = True,
    ) -> Category:
        return get_usable_category(
            self._db,
            membership.household_id,
            category_id,
            require_active=require_active,
        )

    def _assert_not_linked(self, transaction: Transaction) -> None:
        source = self._transactions.linked_source(transaction.id)
        if source is not None:
            raise AppError(
                code="linked_transaction",
                message=(
                    "Cette transaction est liée à une échéance, une dépense prévue "
                    "ou une contribution. Corrigez l'élément source."
                ),
                status_code=409,
            )

    def _validate_amount_change(self, transaction: Transaction, amount_cents: int) -> None:
        if transaction.transaction_type == "expense":
            refunded = self._transactions.sum_refunds(transaction.id)
            if amount_cents < refunded:
                raise self._invalid_refund(
                    "Le montant ne peut pas être inférieur aux remboursements déjà enregistrés."
                )
            return

        if transaction.original_transaction_id is None:
            raise self._invalid_refund()
        original = self._transactions.get_by_id(transaction.original_transaction_id)
        if original is None:
            raise self._invalid_refund()
        other_refunds = self._transactions.sum_refunds(original.id) - transaction.amount_cents
        if amount_cents > original.amount_cents - other_refunds:
            raise self._invalid_refund("Le remboursement dépasse le montant encore remboursable.")

    @staticmethod
    def _not_found() -> AppError:
        return AppError(
            code="not_found",
            message="Transaction introuvable.",
            status_code=404,
        )

    @staticmethod
    def _invalid_budget() -> AppError:
        return AppError(
            code="invalid_budget",
            message=(
                "Le budget courses est obligatoire et réservé aux dépenses communes de courses."
            ),
            status_code=422,
        )

    @staticmethod
    def _invalid_refund(message: str = "Remboursement invalide.") -> AppError:
        return AppError(
            code="invalid_refund",
            message=message,
            status_code=422,
        )
