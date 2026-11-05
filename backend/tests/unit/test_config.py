import pytest
from pydantic import ValidationError

from app.core.config import AppEnv, Settings


def test_database_url_is_built_from_postgres_settings() -> None:
    settings = Settings(
        _env_file=None,
        database_url=None,
        postgres_host="db.local",
        postgres_port=5433,
        postgres_db="famille",
        postgres_user="membre",
        postgres_password="secret",
    )

    assert settings.database_url_effective == (
        "postgresql+psycopg://membre:secret@db.local:5433/famille"
    )


def test_explicit_database_url_takes_precedence() -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://override:override@localhost:5432/override",
        postgres_db="ignored",
    )

    assert settings.database_url_effective.endswith("/override")


def test_password_is_masked_in_settings_repr() -> None:
    settings = Settings(_env_file=None, postgres_password="mot-de-passe-tres-secret")

    assert "mot-de-passe-tres-secret" not in repr(settings)


def test_production_flag() -> None:
    settings = Settings(_env_file=None, app_env=AppEnv.prod, postgres_password="secret")
    assert settings.is_production
    assert not Settings(_env_file=None, app_env=AppEnv.local).is_production


def test_production_rejects_default_password() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_env=AppEnv.prod, database_url=None)
