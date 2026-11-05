import pytest
from starlette.responses import Response

from app.api.middleware import _apply_security_headers, _safe_log_path

pytestmark = pytest.mark.unit


def test_invitation_token_is_removed_from_logged_path() -> None:
    assert (
        _safe_log_path("/api/v1/invitations/secret-token/accept")
        == "/api/v1/invitations/{token}/accept"
    )


def test_regular_path_is_unchanged() -> None:
    assert _safe_log_path("/api/v1/auth/me") == "/api/v1/auth/me"


def test_security_headers_on_api_routes() -> None:
    response = Response()

    _apply_security_headers(response, path="/api/v1/auth/me", production=False)

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "geolocation=()" in response.headers["permissions-policy"]
    assert response.headers["content-security-policy"].startswith("default-src 'none'")
    assert "strict-transport-security" not in response.headers


def test_hsts_is_added_in_production() -> None:
    response = Response()

    _apply_security_headers(response, path="/health/live", production=True)

    assert response.headers["strict-transport-security"] == ("max-age=31536000; includeSubDomains")
