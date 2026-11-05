import logging
import re
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.request_context import request_id_var

logger = logging.getLogger(__name__)

_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_INVITATION_PATH_RE = re.compile(r"(/invitations/)[^/]+(/accept)")


def _request_id_from_header(value: str | None) -> str:
    if value is not None and _REQUEST_ID_RE.fullmatch(value):
        return value
    return str(uuid.uuid4())


def _safe_log_path(path: str) -> str:
    """Ne jamais journaliser le token d'invitation présent dans l'URL."""
    return _INVITATION_PATH_RE.sub(r"\1{token}\2", path)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Ajoute un identifiant de requête et journalise l'accès sans données sensibles."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = _request_id_from_header(request.headers.get("x-request-id"))
        request.state.request_id = request_id
        token = request_id_var.set(request_id)
        started_at = time.perf_counter()
        status_code = 500

        try:
            response = await call_next(request)
            status_code = response.status_code
        finally:
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            logger.info(
                "request",
                extra={
                    "extra_fields": {
                        "method": request.method,
                        "path": _safe_log_path(request.url.path),
                        "status": status_code,
                        "duration_ms": duration_ms,
                    }
                },
            )
            request_id_var.reset(token)

        response.headers["X-Request-ID"] = request_id
        if request.url.path.startswith("/api/v1"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response
