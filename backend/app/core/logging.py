import json
import logging
from datetime import UTC, datetime
from typing import Any

from app.core.config import Settings
from app.core.request_context import request_id_var


class JsonFormatter(logging.Formatter):
    """Format de log JSON minimal, sans données sensibles."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_var.get(),
        }

        extra_fields = getattr(record, "extra_fields", None)
        if isinstance(extra_fields, dict):
            payload.update(extra_fields)

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False)


def configure_logging(settings: Settings) -> None:
    """Configure les logs applicatifs en JSON, sans toucher au contenu des requêtes."""
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(settings.log_level.upper())

    # Le middleware HTTP journalise déjà les accès de manière structurée.
    logging.getLogger("uvicorn.access").disabled = True
