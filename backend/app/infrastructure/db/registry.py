"""Point d'entrée unique pour que tous les modèles soient connus d'Alembic."""

from app.domains.households.models import Household, HouseholdMember
from app.domains.users.models import User

__all__ = ["Household", "HouseholdMember", "User"]
