import hashlib
import secrets
from typing import Final

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError

PASSWORD_MIN_LENGTH: Final = 12
PASSWORD_MAX_LENGTH: Final = 128

# Paramètres Argon2id explicites, adaptés à un usage familial.
_password_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)

# Hachage factice utilisé pour réduire l'écart de temps entre un email inconnu
# et un mot de passe incorrect.
_DUMMY_PASSWORD_HASH = _password_hasher.hash("dummy-password-for-timing")


def validate_password_strength(password: str) -> str:
    if len(password) < PASSWORD_MIN_LENGTH:
        raise ValueError(
            f"Le mot de passe doit contenir au moins {PASSWORD_MIN_LENGTH} caractères."
        )
    if len(password) > PASSWORD_MAX_LENGTH:
        raise ValueError(f"Le mot de passe ne peut pas dépasser {PASSWORD_MAX_LENGTH} caractères.")
    if password.strip() == "":
        raise ValueError("Le mot de passe ne peut pas être vide.")
    return password


def hash_password(password: str) -> str:
    validate_password_strength(password)
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, password)
    except (VerificationError, ValueError):
        # Hash invalide, paramètres non supportés ou mot de passe incorrect.
        return False


def verify_dummy_password(password: str) -> None:
    """Consomme un temps comparable à une vérification réelle."""
    verify_password(password, _DUMMY_PASSWORD_HASH)


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def constant_time_compare(left: str, right: str) -> bool:
    return secrets.compare_digest(left, right)


def normalize_email(email: str) -> str:
    return email.strip().lower()
