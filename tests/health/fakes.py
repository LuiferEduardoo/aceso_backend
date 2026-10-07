from datetime import date, datetime

from aceso.health.domain.entities import (
    DailySummary,
    HealthSample,
    HealthSource,
    SampleMetric,
    SleepSession,
)


class FakeHealthRepository:
    def __init__(self) -> None:
        self.summaries: dict[tuple, DailySummary] = {}
        self.samples: dict[tuple, HealthSample] = {}
        self.sleeps: dict[tuple, SleepSession] = {}

    async def upsert_daily_summaries(self, summaries: list[DailySummary]) -> None:
        for s in summaries:
            self.summaries[(s.user_id, s.source, s.day)] = s

    async def upsert_samples(self, samples: list[HealthSample]) -> None:
        for s in samples:
            self.samples[(s.user_id, s.metric, s.recorded_at, s.source)] = s

    async def upsert_sleep_sessions(self, sessions: list[SleepSession]) -> None:
        for s in sessions:
            self.sleeps[(s.user_id, s.source, s.start_at)] = s

    async def list_daily_summaries(
        self, user_id: int, start: date, end: date, source: HealthSource | None
    ) -> list[DailySummary]:
        return [
            s
            for s in self.summaries.values()
            if s.user_id == user_id and start <= s.day <= end and source in (None, s.source)
        ]

    async def list_samples(
        self,
        user_id: int,
        metric: SampleMetric,
        start: datetime,
        end: datetime,
        source: HealthSource | None,
    ) -> list[HealthSample]:
        return [
            s
            for s in self.samples.values()
            if s.user_id == user_id
            and s.metric == metric
            and start <= s.recorded_at < end
            and source in (None, s.source)
        ]

    async def list_sleep_sessions(
        self, user_id: int, start: datetime, end: datetime, source: HealthSource | None
    ) -> list[SleepSession]:
        return [
            s
            for s in self.sleeps.values()
            if s.user_id == user_id and start <= s.start_at < end and source in (None, s.source)
        ]
