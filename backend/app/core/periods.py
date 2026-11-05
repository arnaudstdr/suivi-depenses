import calendar
from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.core.errors import AppError


def parse_period(period: str) -> tuple[date, date]:
    try:
        start = datetime.strptime(period, "%Y-%m").date().replace(day=1)
    except ValueError as exc:
        raise AppError(
            code="invalid_period",
            message="La période doit être au format YYYY-MM.",
            status_code=422,
        ) from exc
    last_day = calendar.monthrange(start.year, start.month)[1]
    return start, start.replace(day=last_day)


def current_period(timezone: str = "Europe/Paris") -> str:
    return datetime.now(ZoneInfo(timezone)).strftime("%Y-%m")


def add_months(anchor: date, months: int, day: int) -> date:
    month_index = anchor.month - 1 + months
    year = anchor.year + month_index // 12
    month = month_index % 12 + 1
    clamped_day = min(day, calendar.monthrange(year, month)[1])
    return date(year, month, clamped_day)
