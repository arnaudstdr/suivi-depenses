from fastapi import APIRouter

from app.domains.auth.router import invitations_router
from app.domains.auth.router import router as auth_router
from app.domains.households.router import router as households_router
from app.domains.users.router import router as users_router

api_v1_router = APIRouter()
api_v1_router.include_router(auth_router)
api_v1_router.include_router(invitations_router)
api_v1_router.include_router(users_router)
api_v1_router.include_router(households_router)
