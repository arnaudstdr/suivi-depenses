import pytest

from app.core.config import AppEnv, Settings
from app.core.security import (
    constant_time_compare,
    generate_token,
    hash_password,
    hash_token,
    normalize_email,
    validate_password_strength,
    verify_password,
)

pytestmark = pytest.mark.unit


def test_password_hash_uses_argon2id_and_verifies() -> None:
    password_hash = hash_password("correct-horse-battery-staple")

    assert password_hash.startswith("$argon2id$")
    assert verify_password("correct-horse-battery-staple", password_hash)
    assert not verify_password("wrong-password", password_hash)
    assert not verify_password("wrong-password", "not-an-argon2-hash")


def test_short_password_is_rejected() -> None:
    with pytest.raises(ValueError):
        hash_password("court")


def test_password_strength_rejects_blank_password() -> None:
    with pytest.raises(ValueError):
        validate_password_strength("            ")


def test_token_hash_is_deterministic_and_not_reversible() -> None:
    token = generate_token()
    token_hash = hash_token(token)

    assert len(token_hash) == 64
    assert token_hash == hash_token(token)
    assert token not in token_hash


def test_constant_time_compare() -> None:
    assert constant_time_compare("abc", "abc")
    assert not constant_time_compare("abc", "abd")


def test_normalize_email() -> None:
    assert normalize_email("  Alice@Example.COM ") == "alice@example.com"


def test_cookie_secure_defaults_to_production_only() -> None:
    assert not Settings(_env_file=None, app_env=AppEnv.local).cookie_secure_effective
    assert Settings(
        _env_file=None,
        app_env=AppEnv.prod,
        postgres_password="secret",
    ).cookie_secure_effective


def test_cookie_secure_can_be_forced() -> None:
    assert Settings(
        _env_file=None, app_env=AppEnv.local, cookie_secure=True
    ).cookie_secure_effective


def test_samesite_none_requires_secure_cookie() -> None:
    with pytest.raises(ValueError):
        Settings(
            _env_file=None,
            app_env=AppEnv.local,
            cookie_secure=False,
            cookie_samesite="none",
        )
