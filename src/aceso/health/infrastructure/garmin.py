"""Garmin adapter built on the unofficial `garminconnect` client.

Garmin's official Health API is partner-only, so this adapter may break when Garmin
changes its web endpoints. It sits behind the HealthProvider port so it can be replaced.
"""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from typing import Any

from asyncer import asyncify
from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

from aceso.health.domain.entities import (
    DailySummary,
    HealthBatch,
    HealthSample,
    SampleMetric,
    SleepSession,
)
from aceso.shared.domain.errors import IntegrationError, InvalidOperationError


def _from_ms(timestamp_ms: int) -> datetime:
    return datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC)


def _int(value: Any) -> int | None:
    return round(value) if isinstance(value, int | float) else None


def map_daily_summary(day: date, stats: dict[str, Any] | None) -> DailySummary | None:
    if not stats:
        return None
    active_parts = [stats.get("highlyActiveSeconds"), stats.get("activeSeconds")]
    active_minutes = (
        round(sum(p or 0 for p in active_parts) / 60)
        if any(p is not None for p in active_parts)
        else None
    )
    summary = DailySummary(
        day=day,
        steps=_int(stats.get("totalSteps")),
        distance_m=stats.get("totalDistanceMeters"),
        calories_active=_int(stats.get("activeKilocalories")),
        calories_total=_int(stats.get("totalKilocalories")),
        active_minutes=active_minutes,
        resting_hr=_int(stats.get("restingHeartRate")),
        max_hr=_int(stats.get("maxHeartRate")),
        stress_avg=_int(stats.get("averageStressLevel"))
        if (stats.get("averageStressLevel") or 0) >= 0
        else None,
    )
    values = (summary.steps, summary.calories_total, summary.resting_hr, summary.active_minutes)
    return summary if any(v is not None for v in values) else None


def map_sleep(data: dict[str, Any] | None) -> SleepSession | None:
    dto = (data or {}).get("dailySleepDTO") or {}
    start, end = dto.get("sleepStartTimestampGMT"), dto.get("sleepEndTimestampGMT")
    if not start or not end or end <= start:
        return None
    score = ((dto.get("sleepScores") or {}).get("overall") or {}).get("value")
    return SleepSession(
        start_at=_from_ms(start),
        end_at=_from_ms(end),
        deep_s=_int(dto.get("deepSleepSeconds")),
        light_s=_int(dto.get("lightSleepSeconds")),
        rem_s=_int(dto.get("remSleepSeconds")),
        awake_s=_int(dto.get("awakeSleepSeconds")),
        score=_int(score),
    )


def map_series(metric: SampleMetric, values: list[list[Any]] | None) -> list[HealthSample]:
    """Garmin series are [[timestamp_ms, value], ...]; negative stress values mean 'no data'."""
    samples = []
    for entry in values or []:
        if len(entry) < 2 or entry[0] is None or entry[1] is None or entry[1] < 0:
            continue
        samples.append(
            HealthSample(metric=metric, recorded_at=_from_ms(entry[0]), value=float(entry[1]))
        )
    return samples


@contextmanager
def _translate_errors() -> Iterator[None]:
    try:
        yield
    except GarminConnectAuthenticationError as exc:
        raise InvalidOperationError(
            "Garmin rejected the credentials; connect the account again"
        ) from exc
    except GarminConnectTooManyRequestsError as exc:
        raise IntegrationError("Garmin rate limit reached, try again later") from exc
    except (GarminConnectConnectionError, OSError) as exc:
        raise IntegrationError("Could not reach Garmin Connect") from exc


class GarminHealthProvider:
    def __init__(self, client_factory: Callable[..., Any] = Garmin) -> None:
        self._client_factory = client_factory

    async def connect(self, email: str, password: str) -> dict[str, Any]:
        return await asyncify(self._connect)(email, password)

    async def fetch(
        self, credentials: dict[str, Any], start: date, end: date
    ) -> tuple[HealthBatch, dict[str, Any]]:
        return await asyncify(self._fetch)(credentials, start, end)

    def _connect(self, email: str, password: str) -> dict[str, Any]:
        client = self._client_factory(email, password)
        with _translate_errors():
            client.login()
            return {"tokens": client.client.dumps()}

    def _fetch(
        self, credentials: dict[str, Any], start: date, end: date
    ) -> tuple[HealthBatch, dict[str, Any]]:
        if not credentials.get("tokens"):
            raise InvalidOperationError("Garmin credentials are incomplete; connect again")
        client = self._client_factory()
        batch = HealthBatch()
        with _translate_errors():
            client.login(tokenstore=credentials["tokens"])
            day = start
            while day <= end:
                cdate = day.isoformat()
                if summary := map_daily_summary(day, client.get_stats(cdate)):
                    batch.daily_summaries.append(summary)
                if sleep := map_sleep(client.get_sleep_data(cdate)):
                    batch.sleep_sessions.append(sleep)
                heart = client.get_heart_rates(cdate) or {}
                batch.samples += map_series(SampleMetric.HEART_RATE, heart.get("heartRateValues"))
                stress = client.get_stress_data(cdate) or {}
                batch.samples += map_series(SampleMetric.STRESS, stress.get("stressValuesArray"))
                day += timedelta(days=1)
            tokens = client.client.dumps()
        return batch, {"tokens": tokens}
