from enum import StrEnum
from functools import lru_cache

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class AppEnv(StrEnum):
    local = "local"
    test = "test"
    prod = "prod"


class Settings(BaseSettings):
    """Configuration de l'application, lue depuis l'environnement et les fichiers .env."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Suivi de dépenses"
    app_env: AppEnv = AppEnv.local
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"
    docs_enabled: bool = True

    database_url: str | None = None
    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5432
    postgres_db: str = "suivi_depenses"
    postgres_user: str = "suivi"
    postgres_password: SecretStr = SecretStr("change-me-local-only")
    db_echo: bool = False

    sentry_dsn: str | None = None

    @property
    def database_url_effective(self) -> str:
        """URL SQLAlchemy effective, sans exposer le mot de passe dans les logs."""
        if self.database_url:
            return self.database_url

        return URL.create(
            drivername="postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        ).render_as_string(hide_password=False)

    @property
    def is_production(self) -> bool:
        return self.app_env is AppEnv.prod

    @model_validator(mode="after")
    def reject_default_password_in_production(self) -> "Settings":
        if (
            self.is_production
            and self.database_url is None
            and self.postgres_password.get_secret_value() == "change-me-local-only"
        ):
            raise ValueError("POSTGRES_PASSWORD doit être défini en production.")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
