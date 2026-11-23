from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from aceso.planner.domain.entities import DEFAULT_TIMEZONE
from aceso.shared.domain.errors import InvalidOperationError

MAX_RANGE_DAYS = 366
DEFAULT_TZ = ZoneInfo(DEFAULT_TIMEZONE)


def validate_range(start: date, end: date) -> None:
    if end < start:
        raise InvalidOperationError("'to' must be on or after 'from'")
    if (end - start).days > MAX_RANGE_DAYS:
        raise InvalidOperationError(f"Range cannot exceed {MAX_RANGE_DAYS} days")


def day_start(day: date, tz: ZoneInfo = DEFAULT_TZ) -> datetime:
    """The UTC instant at which `day` starts in `tz`."""
    return datetime.combine(day, time.min, tzinfo=tz).astimezone(UTC)


def day_bounds(start: date, end: date, tz: ZoneInfo = DEFAULT_TZ) -> tuple[datetime, datetime]:
    """Half-open UTC range covering the calendar days `start`..`end` in `tz`."""
    return day_start(start, tz), day_start(end + timedelta(days=1), tz)


def local_day(moment: datetime, tz: ZoneInfo = DEFAULT_TZ) -> date:
    """The calendar day (in `tz`) an instant falls on."""
    return moment.astimezone(tz).date()
