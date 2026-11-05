import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        app_env="test",
        database_url="postgresql+psycopg://test:test@127.0.0.1:1/test?connect_timeout=1",
        log_level="WARNING",
    )


@pytest.mark.unit
def test_live_does_not_need_database() -> None:
    with TestClient(create_app(_settings())) as client:
        response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.unit
def test_ready_returns_503_when_database_is_unreachable() -> None:
    with TestClient(create_app(_settings())) as client:
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
