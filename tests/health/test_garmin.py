from datetime import UTC, date, datetime
from typing import Any, ClassVar

import pytest
from garminconnect import GarminConnectAuthenticationError

from aceso.health.application.ingest import IngestHealthData
from aceso.health.application.providers import SyncHealthProvider
from aceso.health.domain.entities import HealthSource, SampleMetric
from aceso.health.infrastructure.garmin import (
    GarminHealthProvider,
    map_daily_summary,
    map_series,
    map_sleep,
)
from aceso.shared.domain.credentials import IntegrationProvider
from aceso.shared.domain.errors import InvalidOperationError, NotFoundError
from tests.health.fakes import FakeHealthRepository

TS = int(datetime(2026, 10, 6, 8, 0, tzinfo=UTC).timestamp() * 1000)

STATS = {
    "totalSteps": 9876,
    "totalDistanceMeters": 7100.5,
    "activeKilocalories": 480.0,
    "totalKilocalories": 2250.0,
    "highlyActiveSeconds": 1200,
    "activeSeconds": 2400,
    "restingHeartRate": 50,
    "maxHeartRate": 158,
    "averageStressLevel": 31,
}
SLEEP = {
    "dailySleepDTO": {
        "sleepStartTimestampGMT": TS - 8 * 3600 * 1000,
        "sleepEndTimestampGMT": TS,
        "deepSleepSeconds": 5000,
        "lightSleepSeconds": 15000,
        "remSleepSeconds": 6000,
        "awakeSleepSeconds": 900,
        "sleepScores": {"overall": {"value": 84}},
    }
}


class FakeGarminSession:
    def __init__(self, tokens: str) -> None:
        self.tokens = tokens

    def dumps(self) -> str:
        return self.tokens


class FakeGarmin:
    """Stands in for garminconnect.Garmin (no network)."""

    instances: ClassVar[list["FakeGarmin"]] = []

    def __init__(self, email: str | None = None, password: str | None = None) -> None:
        self.email, self.password = email, password
        self.client = FakeGarminSession("tokens-v2")
        self.login_args: dict[str, Any] = {}
        FakeGarmin.instances.append(self)

    def login(self, tokenstore: str | None = None) -> tuple[None, None]:
        if self.password == "wrong":
            raise GarminConnectAuthenticationError("401")
        self.login_args = {"tokenstore": tokenstore}
        return None, None

    def get_stats(self, cdate: str) -> dict[str, Any]:
        return STATS

    def get_sleep_data(self, cdate: str) -> dict[str, Any]:
        return SLEEP

    def get_heart_rates(self, cdate: str) -> dict[str, Any]:
        return {"heartRateValues": [[TS, 60], [TS + 120_000, None], [TS + 240_000, 65]]}

    def get_stress_data(self, cdate: str) -> dict[str, Any]:
        return {"stressValuesArray": [[TS, 20], [TS + 180_000, -1]]}


def test_mappers() -> None:
    summary = map_daily_summary(date(2026, 10, 6), STATS)
    assert summary is not None
    assert (summary.steps, summary.active_minutes, summary.calories_total) == (9876, 60, 2250)
    assert map_daily_summary(date(2026, 10, 6), {}) is None

    sleep = map_sleep(SLEEP)
    assert sleep is not None and sleep.score == 84
    assert (sleep.end_at - sleep.start_at).total_seconds() == 8 * 3600
    assert map_sleep({"dailySleepDTO": {}}) is None

    assert [s.value for s in map_series(SampleMetric.STRESS, [[TS, 5], [TS, -2], [TS]])] == [5]


async def test_connect_stores_tokens_not_password() -> None:
    provider = GarminHealthProvider(FakeGarmin)
    assert await provider.connect("me@example.com", "pw") == {"tokens": "tokens-v2"}
    with pytest.raises(InvalidOperationError):
        await provider.connect("me@example.com", "wrong")


async def test_fetch_resumes_session_and_maps_each_day() -> None:
    FakeGarmin.instances.clear()
    provider = GarminHealthProvider(FakeGarmin)
    batch, credentials = await provider.fetch(
        {"tokens": "tokens-v1"}, date(2026, 10, 5), date(2026, 10, 6)
    )
    assert FakeGarmin.instances[0].login_args == {"tokenstore": "tokens-v1"}
    assert credentials == {"tokens": "tokens-v2"}
    assert [s.day for s in batch.daily_summaries] == [date(2026, 10, 5), date(2026, 10, 6)]
    assert len(batch.samples) == 2 * (2 + 1)


class FakeCredentialStore:
    def __init__(self) -> None:
        self.data: dict[tuple[int, IntegrationProvider], dict[str, Any]] = {}

    async def get(self, user_id: int, provider: IntegrationProvider) -> dict[str, Any] | None:
        return self.data.get((user_id, provider))

    async def save(
        self, user_id: int, provider: IntegrationProvider, payload: dict[str, Any]
    ) -> None:
        self.data[(user_id, provider)] = payload

    async def delete(self, user_id: int, provider: IntegrationProvider) -> None:
        self.data.pop((user_id, provider), None)


def _sync(store: FakeCredentialStore, repo: FakeHealthRepository) -> SyncHealthProvider:
    return SyncHealthProvider(
        GarminHealthProvider(FakeGarmin),
        store,
        IngestHealthData(repo),
        IntegrationProvider.GARMIN,
        HealthSource.GARMIN,
    )


async def test_sync_requires_connection_and_saves_refreshed_tokens() -> None:
    store, repo = FakeCredentialStore(), FakeHealthRepository()
    with pytest.raises(NotFoundError):
        await _sync(store, repo).execute(1, date(2026, 10, 6), date(2026, 10, 6))

    await store.save(1, IntegrationProvider.GARMIN, {"tokens": "tokens-v1"})
    result = await _sync(store, repo).execute(1, date(2026, 10, 6), date(2026, 10, 6))

    assert (result.daily_summaries, result.sleep_sessions) == (1, 1)
    assert store.data[(1, IntegrationProvider.GARMIN)] == {"tokens": "tokens-v2"}
    assert {s.source for s in repo.summaries.values()} == {HealthSource.GARMIN}


async def test_sync_rejects_long_ranges() -> None:
    with pytest.raises(InvalidOperationError):
        await _sync(FakeCredentialStore(), FakeHealthRepository()).execute(
            1, date(2026, 9, 1), date(2026, 10, 6)
        )
