from datetime import date, datetime
from typing import Protocol

from aceso.health.domain.entities import (
    DailySummary,
    HealthSample,
    HealthSource,
    SampleMetric,
    SleepSession,
)


class HealthRepository(Protocol):
    """Upserts are idempotent: summaries by (user, source, day), samples by
    (user, metric, recorded_at, source) and sleep by (user, source, start_at)."""

    async def upsert_daily_summaries(self, summaries: list[DailySummary]) -> None: ...

    async def upsert_samples(self, samples: list[HealthSample]) -> None: ...

    async def upsert_sleep_sessions(self, sessions: list[SleepSession]) -> None: ...

    async def list_daily_summaries(
        self, user_id: int, start: date, end: date, source: HealthSource | None
    ) -> list[DailySummary]: ...

    async def list_samples(
        self,
        user_id: int,
        metric: SampleMetric,
        start: datetime,
        end: datetime,
        source: HealthSource | None,
    ) -> list[HealthSample]: ...

    async def list_sleep_sessions(
        self, user_id: int, start: datetime, end: datetime, source: HealthSource | None
    ) -> list[SleepSession]: ...
