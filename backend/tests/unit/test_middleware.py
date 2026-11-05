from app.api.middleware import _safe_log_path


def test_invitation_token_is_removed_from_logged_path() -> None:
    assert (
        _safe_log_path("/api/v1/invitations/secret-token/accept")
        == "/api/v1/invitations/{token}/accept"
    )


def test_regular_path_is_unchanged() -> None:
    assert _safe_log_path("/api/v1/auth/me") == "/api/v1/auth/me"
