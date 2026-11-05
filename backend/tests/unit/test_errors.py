import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.errors import AppError
from app.main import create_app


def _client() -> TestClient:
    settings = Settings(
        _env_file=None,
        app_env="test",
        database_url="postgresql+psycopg://test:test@127.0.0.1:1/test?connect_timeout=1",
        log_level="WARNING",
    )
    return TestClient(create_app(settings))


@pytest.mark.unit
def test_unknown_route_returns_stable_error_envelope() -> None:
    with _client() as client:
        response = client.get("/route-inconnue")

    payload = response.json()
    assert response.status_code == 404
    assert payload["code"] == "not_found"
    assert payload["message"]
    assert set(payload) == {"code", "message", "details", "request_id"}
    assert payload["request_id"] == response.headers["x-request-id"]


@pytest.mark.unit
def test_valid_request_id_is_propagated() -> None:
    with _client() as client:
        response = client.get("/health/live", headers={"X-Request-ID": "abc-123"})

    assert response.headers["x-request-id"] == "abc-123"


@pytest.mark.unit
def test_invalid_request_id_is_replaced() -> None:
    with _client() as client:
        response = client.get("/health/live", headers={"X-Request-ID": "x" * 200})

    assert response.headers["x-request-id"] != "x" * 200
    assert len(response.headers["x-request-id"]) <= 64


@pytest.mark.unit
def test_application_error_uses_stable_envelope() -> None:
    settings = Settings(
        _env_file=None,
        app_env="test",
        database_url="postgresql+psycopg://test:test@127.0.0.1:1/test?connect_timeout=1",
        log_level="WARNING",
    )
    app = create_app(settings)

    @app.get("/boom")
    def boom() -> None:
        raise AppError(code="boom", message="Boum", status_code=409, details={"x": 1})

    with TestClient(app) as client:
        response = client.get("/boom")

    assert response.status_code == 409
    payload = response.json()
    assert payload["code"] == "boom"
    assert payload["message"] == "Boum"
    assert payload["details"] == {"x": 1}
    assert payload["request_id"] == response.headers["x-request-id"]


@pytest.mark.unit
def test_unexpected_error_does_not_leak_details() -> None:
    settings = Settings(
        _env_file=None,
        app_env="test",
        database_url="postgresql+psycopg://test:test@127.0.0.1:1/test?connect_timeout=1",
        log_level="CRITICAL",
    )
    app = create_app(settings)

    @app.get("/crash")
    def crash() -> None:
        raise RuntimeError("secret interne")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/crash")

    assert response.status_code == 500
    payload = response.json()
    assert payload["code"] == "internal_error"
    assert "secret interne" not in payload["message"]
    assert payload["request_id"] == response.headers["x-request-id"]
