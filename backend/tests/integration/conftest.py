from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.main import create_app


@pytest.fixture()
def clean_database(migrated_database_url: str) -> Iterator[None]:
    engine = create_engine(migrated_database_url)
    yield
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE TABLE audit_logs, invitations, sessions, "
                "household_members, households, users CASCADE"
            )
        )
    engine.dispose()


@pytest.fixture()
def test_settings(migrated_database_url: str) -> Settings:
    return Settings(
        _env_file=None,
        app_env="test",
        database_url=migrated_database_url,
        log_level="WARNING",
        cookie_secure=False,
    )


@pytest.fixture()
def app(test_settings: Settings, clean_database: None) -> FastAPI:
    return create_app(test_settings)


@pytest.fixture()
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def db_session(migrated_database_url: str, clean_database: None) -> Iterator[Session]:
    engine = create_engine(migrated_database_url)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        yield session
    engine.dispose()
