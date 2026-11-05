"""Point d'entrée unique pour que tous les modèles soient connus d'Alembic."""

from app.domains.allocations.models import (
    AllocationRule,
    AllocationRuleMember,
    HouseholdContribution,
)
from app.domains.audit.models import AuditLog
from app.domains.auth.models import AuthSession, Invitation
from app.domains.balances.models import PersonalBalanceEntry
from app.domains.budgets.models import Budget, BudgetPeriod
from app.domains.categories.models import Category
from app.domains.households.models import Household, HouseholdMember
from app.domains.imports_exports.models import ImportBatch
from app.domains.notifications.models import Notification, NotificationPreference
from app.domains.planned.models import PlannedExpense
from app.domains.recurring.models import RecurringExpense, RecurringOccurrence
from app.domains.transactions.models import Transaction
from app.domains.users.models import User

__all__ = [
    "AllocationRule",
    "AllocationRuleMember",
    "AuditLog",
    "AuthSession",
    "Budget",
    "BudgetPeriod",
    "Category",
    "Household",
    "HouseholdContribution",
    "HouseholdMember",
    "ImportBatch",
    "Invitation",
    "Notification",
    "NotificationPreference",
    "PersonalBalanceEntry",
    "PlannedExpense",
    "RecurringExpense",
    "RecurringOccurrence",
    "Transaction",
    "User",
]
