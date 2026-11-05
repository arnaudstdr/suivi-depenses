from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.domains.households.models import Household, HouseholdMember
from app.domains.households.service import HouseholdService
from app.domains.users.models import User

OWNER_EMAIL = "owner@example.com"
OWNER_PASSWORD = "correct-horse-battery-staple"
OWNER_FIRST_NAME = "Alice"
HOUSEHOLD_NAME = "Foyer test"

INVITEE_EMAIL = "member@example.com"
INVITEE_PASSWORD = "another-strong-password"
INVITEE_FIRST_NAME = "Bob"


def bootstrap_owner(
    db: Session,
    settings: Settings,
    *,
    email: str = OWNER_EMAIL,
    password: str = OWNER_PASSWORD,
    first_name: str = OWNER_FIRST_NAME,
    household_name: str = HOUSEHOLD_NAME,
) -> tuple[User, Household, HouseholdMember]:
    return HouseholdService(db, settings).bootstrap(
        email=email,
        first_name=first_name,
        household_name=household_name,
        password=password,
    )


def get_csrf(client: TestClient) -> str:
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 200
    return str(response.json()["csrf_token"])


def login(
    client: TestClient,
    *,
    email: str = OWNER_EMAIL,
    password: str = OWNER_PASSWORD,
) -> Response:
    csrf_token = get_csrf(client)
    return client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"X-CSRF-Token": csrf_token},
    )


def create_invitation(
    client: TestClient,
    *,
    email: str = INVITEE_EMAIL,
) -> Response:
    csrf_token = get_csrf(client)
    return client.post(
        "/api/v1/households/me/invitations",
        json={"email": email},
        headers={"X-CSRF-Token": csrf_token},
    )


def accept_invitation(
    client: TestClient,
    *,
    token: str,
    email: str = INVITEE_EMAIL,
    password: str = INVITEE_PASSWORD,
    first_name: str = INVITEE_FIRST_NAME,
) -> Response:
    csrf_token = get_csrf(client)
    return client.post(
        f"/api/v1/invitations/{token}/accept",
        json={"email": email, "first_name": first_name, "password": password},
        headers={"X-CSRF-Token": csrf_token},
    )


def setup_two_member_household(
    client: TestClient,
    db: Session,
    settings: Settings,
) -> tuple[str, str]:
    """Crée le foyer, invite le second membre et laisse le client connecté owner."""
    bootstrap_owner(db, settings)
    assert login(client).status_code == 200
    owner_id = str(client.get("/api/v1/auth/me").json()["user"]["id"])
    invitation = create_invitation(client, email=INVITEE_EMAIL)
    assert invitation.status_code == 201
    client.cookies.clear()
    accepted = accept_invitation(
        client,
        token=invitation.json()["token"],
        email=INVITEE_EMAIL,
        first_name=INVITEE_FIRST_NAME,
        password=INVITEE_PASSWORD,
    )
    assert accepted.status_code == 201
    member_id = str(accepted.json()["user"]["id"])
    client.cookies.clear()
    assert login(client).status_code == 200
    return owner_id, member_id
