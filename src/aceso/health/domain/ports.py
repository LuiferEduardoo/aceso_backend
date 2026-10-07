from datetime import date, datetime
from typing import Any, Protocol

from aceso.health.domain.entities import (
    DailySummary,
    HealthBatch,
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


class HealthProvider(Protocol):
    """A wearable platform we pull data from (e.g. Garmin)."""

    async def connect(self, email: str, password: str) -> dict[str, Any]:
        """Authenticate and return the credentials payload to store (never the password)."""
        ...

    async def fetch(
        self, credentials: dict[str, Any], start: date, end: date
    ) -> tuple[HealthBatch, dict[str, Any]]:
        """Return the data for [start, end] and the (possibly refreshed) credentials."""
        ...
