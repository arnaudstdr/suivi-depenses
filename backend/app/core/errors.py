import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.request_context import request_id_var

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Erreur applicative portant un code stable et un statut HTTP."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        status_code: int = 400,
        details: Any = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


_HTTP_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    422: "validation_error",
    500: "internal_error",
}


def _request_id(request: Request) -> str | None:
    state_request_id = getattr(request.state, "request_id", None)
    return state_request_id or request_id_var.get()


def _payload(
    *,
    code: str,
    message: str,
    request_id: str | None,
    details: Any = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "details": details,
        "request_id": request_id,
    }


def _response_headers(request_id: str | None) -> dict[str, str]:
    if request_id is None:
        return {}
    return {"X-Request-ID": request_id}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        request_id = _request_id(request)
        return JSONResponse(
            status_code=exc.status_code,
            content=_payload(
                code=exc.code,
                message=exc.message,
                details=exc.details,
                request_id=request_id,
            ),
            headers=_response_headers(request_id),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        request_id = _request_id(request)
        code = _HTTP_CODES.get(exc.status_code, "http_error")
        message = exc.detail if isinstance(exc.detail, str) else "Erreur HTTP"
        return JSONResponse(
            status_code=exc.status_code,
            content=_payload(code=code, message=message, request_id=request_id),
            headers={**(exc.headers or {}), **_response_headers(request_id)},
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        request_id = _request_id(request)
        # Ne pas renvoyer les valeurs saisies : elles peuvent contenir des secrets.
        details = [
            {"loc": list(error["loc"]), "msg": error["msg"], "type": error["type"]}
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=_payload(
                code="validation_error",
                message="Les données envoyées sont invalides.",
                details=jsonable_encoder(details),
                request_id=request_id,
            ),
            headers=_response_headers(request_id),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        request_id = _request_id(request)
        logger.error(
            "unhandled_exception",
            extra={
                "extra_fields": {
                    "error_type": type(exc).__name__,
                    "request_id": request_id,
                }
            },
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        return JSONResponse(
            status_code=500,
            content=_payload(
                code="internal_error",
                message="Une erreur interne est survenue.",
                request_id=request_id,
            ),
            headers=_response_headers(request_id),
        )
