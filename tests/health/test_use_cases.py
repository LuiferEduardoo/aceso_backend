from datetime import UTC, date, datetime, timedelta

import pytest

from aceso.health.application.ingest import IngestHealthData
from aceso.health.application.queries import HealthQueries
from aceso.health.domain.entities import (
    DailySummary,
    HealthBatch,
    HealthSample,
    HealthSource,
    SampleMetric,
    SleepSession,
)
from aceso.shared.domain.errors import InvalidOperationError
from tests.health.fakes import FakeHealthRepository

T0 = datetime(2026, 10, 6, 23, 0, tzinfo=UTC)


async def test_ingest_stamps_user_and_source_and_dedupes() -> None:
    repo = FakeHealthRepository()
    batch = HealthBatch(
        daily_summaries=[
            DailySummary(day=date(2026, 10, 6), steps=1000),
            DailySummary(day=date(2026, 10, 6), steps=12000),
        ],
        samples=[
            HealthSample(metric=SampleMetric.HEART_RATE, recorded_at=T0, value=60),
            HealthSample(metric=SampleMetric.HEART_RATE, recorded_at=T0, value=62),
            HealthSample(metric=SampleMetric.STRESS, recorded_at=T0, value=20),
        ],
        sleep_sessions=[SleepSession(start_at=T0, end_at=T0 + timedelta(hours=7))],
    )

    result = await IngestHealthData(repo).execute(7, HealthSource.MI_FITNESS, batch)

    assert (result.daily_summaries, result.samples, result.sleep_sessions) == (1, 2, 1)
    summary = next(iter(repo.summaries.values()))
    assert (summary.user_id, summary.source, summary.steps) == (7, "mi_fitness", 12000)
    assert sorted(s.value for s in repo.samples.values()) == [20, 62]


async def test_ingest_rejects_inverted_sleep() -> None:
    batch = HealthBatch(sleep_sessions=[SleepSession(start_at=T0, end_at=T0)])
    with pytest.raises(InvalidOperationError):
        await IngestHealthData(FakeHealthRepository()).execute(1, HealthSource.MANUAL, batch)


async def test_queries_validate_ranges() -> None:
    queries = HealthQueries(FakeHealthRepository())
    with pytest.raises(InvalidOperationError):
        await queries.daily_summaries(1, date(2026, 10, 2), date(2026, 10, 1))
    with pytest.raises(InvalidOperationError):
        await queries.samples(1, SampleMetric.HEART_RATE, T0, T0 + timedelta(days=40))


async def test_sleep_query_covers_whole_end_day() -> None:
    repo = FakeHealthRepository()
    await IngestHealthData(repo).execute(
        1,
        HealthSource.GARMIN,
        HealthBatch(sleep_sessions=[SleepSession(start_at=T0, end_at=T0 + timedelta(hours=8))]),
    )
    queries = HealthQueries(repo)
    assert len(await queries.sleep_sessions(1, date(2026, 10, 6), date(2026, 10, 6))) == 1
    assert await queries.sleep_sessions(1, date(2026, 10, 7), date(2026, 10, 7)) == []
