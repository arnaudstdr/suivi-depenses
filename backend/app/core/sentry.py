from typing import Any

import sentry_sdk

from app.core.config import AppEnv, Settings


def _before_send(event: dict[str, Any], _hint: dict[str, Any]) -> dict[str, Any]:
    # Ne jamais transmettre requête, cookies, en-têtes ni corps à Sentry.
    event.pop("request", None)
    event.pop("breadcrumbs", None)
    return event


def init_sentry(settings: Settings) -> None:
    if settings.app_env is AppEnv.test or not settings.sentry_dsn:
        return

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env.value,
        send_default_pii=False,
        max_request_body_size="never",
        traces_sample_rate=0.0,
        before_send=_before_send,  # type: ignore[arg-type]
    )
