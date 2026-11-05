import uuid
from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.core.errors import AppError
from app.core.periods import current_period, parse_period
from app.core.request_context import request_id_var
from app.domains.allocations.models import AllocationRule, HouseholdContribution
from app.domains.allocations.repository import AllocationRepository
from app.domains.allocations.rounding import split_signed_amount
from app.domains.allocations.schemas import ContributionMarkTransferred
from app.domains.allocations.service import ensure_default_allocation_rule
from app.domains.audit.repository import AuditRepository
from app.domains.budgets.repository import BudgetRepository
from app.domains.budgets.service import ensure_grocery_budget
from app.domains.categories.constants import PARTICIPATION_CATEGORY_ID
from app.domains.categories.models import Category
from app.domains.categories.seed import ensure_default_categories
from app.domains.households.models import HouseholdMember
from app.domains.households.repository import HouseholdRepository
from app.domains.planned.models import PlannedExpense
from app.domains.recurring.models import RecurringExpense, RecurringOccurrence
from app.domains.transactions.models import Transaction
from app.domains.transactions.schemas import TransactionCreate
from app.domains.transactions.service import TransactionService
from app.domains.users.models import User


class ContributionService:
    def __init__(
        self,
        db: Session,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._db = db
        self._now = now or utcnow
        self._allocations = AllocationRepository(db)
        self._households = HouseholdRepository(db)
        self._audit = AuditRepository(db)

    def list_contributions(
        self,
        membership: HouseholdMember,
        period: str | None,
    ) -> list[HouseholdContribution]:
        default_rule = ensure_default_allocation_rule(
            self._db,
            membership.household_id,
        )
        if default_rule is None:
            raise AppError(
                code="no_household_members",
                message="Aucun membre actif dans le foyer.",
                status_code=409,
            )

        period_value = period or current_period(membership.household.timezone)
        start, end = parse_period(period_value)
        percentages = {member.user_id: member.percentage for member in default_rule.members}
        shares = {member.user_id: 0 for member in default_rule.members}
        self._add_recurring_shares(
            shares,
            membership.household_id,
            start,
            end,
            default_rule,
        )
        self._add_planned_shares(
            shares,
            membership.household_id,
            start,
            end,
            default_rule,
        )
        self._add_transaction_shares(
            shares,
            membership.household_id,
            start,
            end,
            default_rule,
        )
        self._add_grocery_share(
            shares,
            membership.household_id,
            start,
            default_rule,
        )

        active_members = [
            member
            for member in self._households.list_members(membership.household_id)
            if member.is_active
        ]
        for member in active_members:
            amount_cents = max(shares.get(member.user_id, 0), 0)
            percentage = percentages.get(member.user_id, Decimal("0"))
            contribution = self._allocations.get_contribution(
                membership.household_id,
                member.user_id,
                start,
            )
            if contribution is None:
                self._allocations.add_contribution(
                    HouseholdContribution(
                        household_id=membership.household_id,
                        user_id=member.user_id,
                        period_start=start,
                        amount_cents=amount_cents,
                        allocation_percentage=percentage,
                        status="pending",
                    )
                )
            elif contribution.status == "pending":
                contribution.amount_cents = amount_cents
                contribution.allocation_percentage = percentage

        self._db.commit()
        return self._allocations.list_contributions(
            membership.household_id,
            start,
        )

    def mark_transferred(
        self,
        membership: HouseholdMember,
        user: User,
        contribution_id: uuid.UUID,
        payload: ContributionMarkTransferred,
    ) -> HouseholdContribution:
        contribution = self._allocations.get_contribution_for_update(contribution_id)
        if contribution is None or contribution.household_id != membership.household_id:
            raise AppError(
                code="not_found",
                message="Contribution introuvable.",
                status_code=404,
            )
        if contribution.user_id != user.id:
            raise AppError(
                code="forbidden",
                message="Chaque membre pointe uniquement sa propre contribution.",
                status_code=403,
            )
        if contribution.status == "transferred":
            return contribution
        if contribution.status == "cancelled":
            raise AppError(
                code="contribution_cancelled",
                message="Cette contribution est annulée.",
                status_code=409,
            )

        ensure_default_categories(self._db)
        transferred_local = payload.transferred_at.astimezone(
            ZoneInfo(membership.household.timezone)
        )
        transaction = TransactionService(self._db, self._now).create(
            membership,
            user,
            TransactionCreate(
                label=(f"Participation au foyer {contribution.period_start.strftime('%Y-%m')}"),
                amount_cents=payload.transferred_amount_cents,
                transaction_date=transferred_local.date(),
                category_id=PARTICIPATION_CATEGORY_ID,
                scope="personal",
                transaction_type="expense",
                paid_at=payload.transferred_at,
                notes=payload.note,
            ),
            commit=False,
            allow_inactive_category=True,
        )

        contribution.status = "transferred"
        contribution.transferred_at = payload.transferred_at
        contribution.transferred_amount_cents = payload.transferred_amount_cents
        contribution.transaction_id = transaction.id

        self._audit.add(
            occurred_at=self._now(),
            action="household_contribution.transferred",
            entity_type="household_contribution",
            entity_id=contribution.id,
            actor_user_id=user.id,
            household_id=membership.household_id,
            request_id=request_id_var.get(),
        )
        self._db.commit()
        return contribution

    def _add_recurring_shares(
        self,
        shares: dict[uuid.UUID, int],
        household_id: uuid.UUID,
        start: date,
        end: date,
        default_rule: AllocationRule,
    ) -> None:
        rows = self._db.execute(
            select(RecurringOccurrence, RecurringExpense)
            .join(
                RecurringExpense,
                RecurringOccurrence.recurring_expense_id == RecurringExpense.id,
            )
            .join(Category, RecurringExpense.category_id == Category.id)
            .where(
                RecurringExpense.household_id == household_id,
                RecurringExpense.scope == "shared",
                Category.is_grocery.is_(False),
                RecurringOccurrence.due_date >= start,
                RecurringOccurrence.due_date <= end,
                RecurringOccurrence.status.in_(["pending", "confirmed", "paid"]),
            )
        ).all()

        for occurrence, recurring in rows:
            if occurrence.status == "paid":
                amount = occurrence.payment_amount_cents
            else:
                amount = occurrence.confirmed_amount_cents or occurrence.expected_amount_cents
            if amount is None:
                continue
            rule = self._resolve_rule(recurring, default_rule)
            self._add_split(shares, amount, rule)

    def _add_planned_shares(
        self,
        shares: dict[uuid.UUID, int],
        household_id: uuid.UUID,
        start: date,
        end: date,
        default_rule: AllocationRule,
    ) -> None:
        rows = self._db.execute(
            select(PlannedExpense, Transaction.amount_cents)
            .join(Category, PlannedExpense.category_id == Category.id)
            .outerjoin(
                Transaction,
                PlannedExpense.transaction_id == Transaction.id,
            )
            .where(
                PlannedExpense.household_id == household_id,
                PlannedExpense.scope == "shared",
                Category.is_grocery.is_(False),
                PlannedExpense.planned_date >= start,
                PlannedExpense.planned_date <= end,
                PlannedExpense.status.in_(["planned", "committed", "paid"]),
            )
        ).all()

        for planned, transaction_amount in rows:
            amount = (
                transaction_amount
                if planned.status == "paid" and transaction_amount is not None
                else planned.amount_cents
            )
            self._add_split(shares, amount, default_rule)

    def _add_transaction_shares(
        self,
        shares: dict[uuid.UUID, int],
        household_id: uuid.UUID,
        start: date,
        end: date,
        default_rule: AllocationRule,
    ) -> None:
        planned_transaction_ids = select(PlannedExpense.transaction_id).where(
            PlannedExpense.transaction_id.is_not(None)
        )
        rows = self._db.execute(
            select(Transaction)
            .join(Category, Transaction.category_id == Category.id)
            .where(
                Transaction.household_id == household_id,
                Transaction.scope == "shared",
                Transaction.deleted_at.is_(None),
                Transaction.transaction_date >= start,
                Transaction.transaction_date <= end,
                Category.is_grocery.is_(False),
                Transaction.recurring_occurrence_id.is_(None),
                Transaction.id.not_in(planned_transaction_ids),
            )
        ).scalars()

        for transaction in rows:
            amount = (
                transaction.amount_cents
                if transaction.transaction_type == "expense"
                else -transaction.amount_cents
            )
            self._add_split(shares, amount, default_rule)

    def _add_grocery_share(
        self,
        shares: dict[uuid.UUID, int],
        household_id: uuid.UUID,
        start: date,
        default_rule: AllocationRule,
    ) -> None:
        budget = ensure_grocery_budget(self._db, household_id)
        budget_period = BudgetRepository(self._db).get_period(budget.id, start)
        allocated = (
            budget_period.allocated_amount_cents
            if budget_period is not None
            else budget.default_amount_cents
        )
        self._add_split(shares, allocated, default_rule)

    def _resolve_rule(
        self,
        recurring: RecurringExpense,
        default_rule: AllocationRule,
    ) -> AllocationRule:
        if recurring.allocation_rule_id is not None:
            rule = self._allocations.get_rule(recurring.allocation_rule_id)
            if rule is not None and rule.members:
                return rule
        return default_rule

    @staticmethod
    def _add_split(
        shares: dict[uuid.UUID, int],
        amount_cents: int,
        rule: AllocationRule,
    ) -> None:
        if not rule.members:
            return
        percentages = {member.user_id: member.percentage for member in rule.members}
        for user_id, share in split_signed_amount(amount_cents, percentages).items():
            shares[user_id] = shares.get(user_id, 0) + share
