import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings

pytestmark = pytest.mark.integration


def test_api_responses_include_security_headers(
    client: TestClient,
    test_settings: Settings,
) -> None:
    response = client.get("/api/v1/auth/csrf")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "geolocation=()" in response.headers["permissions-policy"]
    assert response.headers["content-security-policy"].startswith("default-src 'none'")
    assert "strict-transport-security" not in response.headers


def test_health_response_also_gets_security_headers(client: TestClient) -> None:
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
