from datetime import UTC, date, datetime, time, timedelta

from aceso.health.domain.entities import (
    DailySummary,
    HealthSample,
    HealthSource,
    SampleMetric,
    SleepSession,
)
from aceso.health.domain.ports import HealthRepository
from aceso.shared.domain.errors import InvalidOperationError

MAX_DAYS = 366
MAX_SAMPLE_RANGE = timedelta(days=31)


def _check_dates(start: date, end: date) -> None:
    if end < start:
        raise InvalidOperationError("'to' must be on or after 'from'")
    if (end - start).days > MAX_DAYS:
        raise InvalidOperationError(f"Range cannot exceed {MAX_DAYS} days")


class HealthQueries:
    def __init__(self, repository: HealthRepository) -> None:
        self._repository = repository

    async def daily_summaries(
        self, user_id: int, start: date, end: date, source: HealthSource | None = None
    ) -> list[DailySummary]:
        _check_dates(start, end)
        return await self._repository.list_daily_summaries(user_id, start, end, source)

    async def samples(
        self,
        user_id: int,
        metric: SampleMetric,
        start: datetime,
        end: datetime,
        source: HealthSource | None = None,
    ) -> list[HealthSample]:
        if end <= start:
            raise InvalidOperationError("'to' must be after 'from'")
        if end - start > MAX_SAMPLE_RANGE:
            raise InvalidOperationError("Sample range cannot exceed 31 days")
        return await self._repository.list_samples(user_id, metric, start, end, source)

    async def sleep_sessions(
        self, user_id: int, start: date, end: date, source: HealthSource | None = None
    ) -> list[SleepSession]:
        """Sleep sessions that started between `start` 00:00 UTC and the end of `end` (UTC)."""
        _check_dates(start, end)
        start_at = datetime.combine(start, time.min, tzinfo=UTC)
        end_at = datetime.combine(end + timedelta(days=1), time.min, tzinfo=UTC)
        return await self._repository.list_sleep_sessions(user_id, start_at, end_at, source)
