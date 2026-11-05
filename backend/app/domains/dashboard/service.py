from collections.abc import Callable
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.core.errors import AppError
from app.core.periods import current_period, parse_period
from app.domains.allocations.contributions import ContributionService
from app.domains.allocations.models import HouseholdContribution
from app.domains.balances.repository import PersonalBalanceRepository
from app.domains.budgets.service import BudgetService
from app.domains.dashboard.repository import DashboardRepository
from app.domains.dashboard.schemas import (
    DashboardBalance,
    DashboardDeductions,
    DashboardGroceryBudget,
    DashboardRecentTransaction,
    DashboardResponse,
    DashboardUpcomingRecurring,
)
from app.domains.households.models import HouseholdMember
from app.domains.planned.models import PlannedExpense
from app.domains.recurring.models import RecurringExpense, RecurringOccurrence
from app.domains.transactions.models import Transaction
from app.domains.users.models import User


class DashboardService:
    def __init__(
        self,
        db: Session,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._db = db
        self._now = now or utcnow
        self._balances = PersonalBalanceRepository(db)
        self._dashboard = DashboardRepository(db)

    def get_dashboard(
        self,
        membership: HouseholdMember,
        user: User,
        period: str | None,
    ) -> DashboardResponse:
        current = current_period(membership.household.timezone)
        if period is not None and period != current:
            raise AppError(
                code="unsupported_period",
                message="Le tableau de bord ne calcule que le mois courant.",
                status_code=422,
            )
        start, end = parse_period(current)
        timezone = ZoneInfo(membership.household.timezone)
        start_at = datetime.combine(start, time.min, tzinfo=timezone).astimezone(UTC)
        end_at = datetime.combine(
            end + timedelta(days=1),
            time.min,
            tzinfo=timezone,
        ).astimezone(UTC)

        balance = self._balances.get_latest(user.id)
        if balance is None:
            raise AppError(
                code="balance_required",
                message="Saisissez d'abord un solde personnel.",
                status_code=409,
            )
        snapshot_at = balance.recorded_at

        recurring_rows = self._dashboard.personal_recurring(
            user.id,
            start,
            end,
            start_at,
            end_at,
        )
        recurring_cents = 0
        upcoming: list[DashboardUpcomingRecurring] = []
        for occurrence, recurring in recurring_rows:
            recurring_cents += self._recurring_amount(
                occurrence,
                recurring,
                snapshot_at,
            )
            if occurrence.status in {"pending", "confirmed"}:
                upcoming.append(
                    DashboardUpcomingRecurring(
                        occurrence_id=occurrence.id,
                        recurring_expense_id=recurring.id,
                        label=recurring.label,
                        due_date=occurrence.due_date,
                        amount_cents=self._recurring_upcoming_amount(
                            occurrence,
                            recurring,
                        ),
                        status=occurrence.status,
                    )
                )
        upcoming.sort(key=lambda item: item.due_date)

        planned_cents = sum(
            self._planned_amount(planned, paid_at, amount, snapshot_at)
            for planned, paid_at, amount in self._dashboard.personal_planned(
                user.id,
                start,
                end,
            )
        )

        transaction_cents = sum(
            self._transaction_amount(transaction, snapshot_at)
            for transaction in self._dashboard.personal_transactions_for_deduction(
                user.id,
                start,
                end,
            )
        )

        contributions = ContributionService(self._db, self._now).list_contributions(
            membership,
            current,
        )
        contribution = next(
            (item for item in contributions if item.user_id == user.id),
            None,
        )
        contribution_cents = self._contribution_amount(
            contribution,
            snapshot_at,
        )
        contribution_status = contribution.status if contribution else "none"

        grocery = BudgetService(self._db, self._now).get_grocery_summary(
            membership,
            current,
        )

        total_cents = recurring_cents + planned_cents + transaction_cents + contribution_cents
        available_cents = balance.balance_cents - total_cents

        recent = self._dashboard.recent_personal_transactions(
            user.id,
            start,
            end,
        )

        return DashboardResponse(
            period=current,
            currency=membership.household.currency,
            personal_balance=DashboardBalance(
                balance_cents=balance.balance_cents,
                recorded_at=balance.recorded_at,
            ),
            deductions=DashboardDeductions(
                personal_recurring_remaining_cents=recurring_cents,
                personal_planned_remaining_cents=planned_cents,
                personal_transactions_remaining_cents=transaction_cents,
                household_contribution_remaining_cents=contribution_cents,
                household_contribution_status=contribution_status,
                total_cents=total_cents,
            ),
            available_forecast_cents=available_cents,
            grocery_budget=DashboardGroceryBudget(
                allocated_cents=grocery.allocated_cents,
                spent_cents=grocery.spent_cents,
                remaining_cents=grocery.remaining_cents,
            ),
            upcoming_recurring=upcoming[:10],
            recent_personal_transactions=[
                DashboardRecentTransaction(
                    id=transaction.id,
                    label=transaction.label,
                    amount_cents=transaction.amount_cents,
                    transaction_date=transaction.transaction_date,
                    category_id=transaction.category_id,
                    transaction_type=transaction.transaction_type,
                )
                for transaction in recent
            ],
        )

    @staticmethod
    def _recurring_amount(
        occurrence: RecurringOccurrence,
        recurring: RecurringExpense,
        snapshot_at: datetime,
    ) -> int:
        if occurrence.status == "skipped":
            return 0
        if occurrence.status == "paid":
            if occurrence.paid_at is None or occurrence.paid_at > snapshot_at:
                return (
                    occurrence.payment_amount_cents
                    or occurrence.expected_amount_cents
                    or recurring.amount_cents
                    or 0
                )
            return 0
        return (
            occurrence.confirmed_amount_cents
            or occurrence.expected_amount_cents
            or recurring.amount_cents
            or 0
        )

    @staticmethod
    def _recurring_upcoming_amount(
        occurrence: RecurringOccurrence,
        recurring: RecurringExpense,
    ) -> int:
        return (
            occurrence.confirmed_amount_cents
            or occurrence.expected_amount_cents
            or recurring.amount_cents
            or 0
        )

    @staticmethod
    def _planned_amount(
        planned: PlannedExpense,
        transaction_paid_at: datetime | None,
        transaction_amount_cents: int | None,
        snapshot_at: datetime,
    ) -> int:
        if planned.status == "cancelled":
            return 0
        if planned.status == "paid":
            if transaction_paid_at is None or transaction_paid_at > snapshot_at:
                return (
                    transaction_amount_cents
                    if transaction_amount_cents is not None
                    else planned.amount_cents
                )
            return 0
        return planned.amount_cents

    @staticmethod
    def _transaction_amount(
        transaction: Transaction,
        snapshot_at: datetime,
    ) -> int:
        if transaction.paid_at is None or transaction.paid_at > snapshot_at:
            return (
                transaction.amount_cents
                if transaction.transaction_type == "expense"
                else -transaction.amount_cents
            )
        return 0

    @staticmethod
    def _contribution_amount(
        contribution: HouseholdContribution | None,
        snapshot_at: datetime,
    ) -> int:
        if contribution is None:
            return 0
        if contribution.status == "pending":
            return contribution.amount_cents
        if contribution.status == "transferred":
            if contribution.transferred_at is None or contribution.transferred_at > snapshot_at:
                return contribution.transferred_amount_cents or contribution.amount_cents
            return 0
        return 0
