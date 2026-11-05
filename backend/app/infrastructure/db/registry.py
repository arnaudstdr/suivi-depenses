"""Point d'entrée unique pour que tous les modèles soient connus d'Alembic."""

from app.domains.audit.models import AuditLog
from app.domains.auth.models import AuthSession, Invitation
from app.domains.balances.models import PersonalBalanceEntry
from app.domains.budgets.models import Budget, BudgetPeriod
from app.domains.categories.models import Category
from app.domains.households.models import Household, HouseholdMember
from app.domains.transactions.models import Transaction
from app.domains.users.models import User

__all__ = [
    "AuditLog",
    "AuthSession",
    "Budget",
    "BudgetPeriod",
    "Category",
    "Household",
    "HouseholdMember",
    "Invitation",
    "PersonalBalanceEntry",
    "Transaction",
    "User",
]
