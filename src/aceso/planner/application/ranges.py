from datetime import UTC, date, datetime, time, timedelta

from aceso.shared.domain.errors import InvalidOperationError

MAX_RANGE_DAYS = 366


def validate_range(start: date, end: date) -> None:
    if end < start:
        raise InvalidOperationError("'to' must be on or after 'from'")
    if (end - start).days > MAX_RANGE_DAYS:
        raise InvalidOperationError(f"Range cannot exceed {MAX_RANGE_DAYS} days")


def day_bounds(start: date, end: date) -> tuple[datetime, datetime]:
    """Half-open UTC range covering the days `start`..`end`."""
    return (
        datetime.combine(start, time.min, tzinfo=UTC),
        datetime.combine(end + timedelta(days=1), time.min, tzinfo=UTC),
    )
