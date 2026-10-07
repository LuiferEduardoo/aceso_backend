from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum


class HealthSource(StrEnum):
    GARMIN = "garmin"
    MI_FITNESS = "mi_fitness"
    HEALTH_CONNECT = "health_connect"
    MANUAL = "manual"


class SampleMetric(StrEnum):
    HEART_RATE = "heart_rate"
    STRESS = "stress"
    SPO2 = "spo2"
    RESPIRATION = "respiration"
    BODY_BATTERY = "body_battery"


@dataclass(slots=True)
class DailySummary:
    day: date
    steps: int | None = None
    distance_m: float | None = None
    calories_active: int | None = None
    calories_total: int | None = None
    active_minutes: int | None = None
    resting_hr: int | None = None
    avg_hr: int | None = None
    max_hr: int | None = None
    stress_avg: int | None = None
    user_id: int | None = None
    source: HealthSource | None = None


@dataclass(slots=True)
class HealthSample:
    metric: SampleMetric
    recorded_at: datetime
    value: float
    user_id: int | None = None
    source: HealthSource | None = None


@dataclass(slots=True)
class SleepSession:
    start_at: datetime
    end_at: datetime
    deep_s: int | None = None
    light_s: int | None = None
    rem_s: int | None = None
    awake_s: int | None = None
    score: int | None = None
    user_id: int | None = None
    source: HealthSource | None = None


@dataclass(slots=True)
class HealthBatch:
    """Data from any provider, ready to be stored for one user and source."""

    daily_summaries: list[DailySummary] = field(default_factory=list)
    samples: list[HealthSample] = field(default_factory=list)
    sleep_sessions: list[SleepSession] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class IngestResult:
    daily_summaries: int
    samples: int
    sleep_sessions: int
