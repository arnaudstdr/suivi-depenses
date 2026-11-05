from fastapi import APIRouter

from app.domains.allocations.router import (
    contributions_router,
    recurring_allocations_router,
    rules_router,
)
from app.domains.auth.router import invitations_router
from app.domains.auth.router import router as auth_router
from app.domains.balances.router import router as balances_router
from app.domains.budgets.router import router as budgets_router
from app.domains.categories.router import router as categories_router
from app.domains.dashboard.router import router as dashboard_router
from app.domains.households.router import router as households_router
from app.domains.planned.router import router as planned_router
from app.domains.recurring.router import occurrences_router
from app.domains.recurring.router import router as recurring_router
from app.domains.transactions.router import router as transactions_router
from app.domains.users.router import router as users_router

api_v1_router = APIRouter()
api_v1_router.include_router(auth_router)
api_v1_router.include_router(invitations_router)
api_v1_router.include_router(users_router)
api_v1_router.include_router(households_router)
api_v1_router.include_router(balances_router)
api_v1_router.include_router(categories_router)
api_v1_router.include_router(transactions_router)
api_v1_router.include_router(budgets_router)
api_v1_router.include_router(planned_router)
api_v1_router.include_router(recurring_router)
api_v1_router.include_router(occurrences_router)
api_v1_router.include_router(rules_router)
api_v1_router.include_router(contributions_router)
api_v1_router.include_router(recurring_allocations_router)
api_v1_router.include_router(dashboard_router)
