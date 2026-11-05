from starlette.responses import Response

from app.core.config import Settings


def set_session_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_ttl_seconds,
        path="/",
        secure=settings.cookie_secure_effective,
        httponly=True,
        samesite=settings.cookie_samesite,
    )


def clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/",
        secure=settings.cookie_secure_effective,
        httponly=True,
        samesite=settings.cookie_samesite,
    )


def set_csrf_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=token,
        max_age=settings.session_ttl_seconds,
        path="/",
        secure=settings.cookie_secure_effective,
        httponly=False,
        samesite=settings.cookie_samesite,
    )
