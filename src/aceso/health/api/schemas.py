from datetime import date, datetime
from typing import Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from aceso.health.domain.entities import (
    DailySummary,
    HealthBatch,
    HealthSample,
    HealthSource,
    SampleMetric,
    SleepSession,
)

MAX_ITEMS = 10_000


class DailySummaryIn(BaseModel):
    day: date
    steps: int | None = Field(default=None, ge=0)
    distance_m: float | None = Field(default=None, ge=0)
    calories_active: int | None = Field(default=None, ge=0)
    calories_total: int | None = Field(default=None, ge=0)
    active_minutes: int | None = Field(default=None, ge=0)
    resting_hr: int | None = Field(default=None, gt=0, lt=300)
    avg_hr: int | None = Field(default=None, gt=0, lt=300)
    max_hr: int | None = Field(default=None, gt=0, lt=300)
    stress_avg: int | None = Field(default=None, ge=0, le=100)


class HealthSampleIn(BaseModel):
    metric: SampleMetric
    recorded_at: AwareDatetime
    value: float


class SleepSessionIn(BaseModel):
    start_at: AwareDatetime
    end_at: AwareDatetime
    deep_s: int | None = Field(default=None, ge=0)
    light_s: int | None = Field(default=None, ge=0)
    rem_s: int | None = Field(default=None, ge=0)
    awake_s: int | None = Field(default=None, ge=0)
    score: int | None = Field(default=None, ge=0, le=100)

    @model_validator(mode="after")
    def _ends_after_start(self) -> Self:
        if self.end_at <= self.start_at:
            raise ValueError("end_at must be after start_at")
        return self


class HealthIngestRequest(BaseModel):
    source: HealthSource = Field(
        description="Where the data comes from, e.g. `health_connect` for Mi Fitness via the app"
    )
    daily_summaries: list[DailySummaryIn] = Field(default=[], max_length=MAX_ITEMS)
    samples: list[HealthSampleIn] = Field(default=[], max_length=MAX_ITEMS)
    sleep_sessions: list[SleepSessionIn] = Field(default=[], max_length=MAX_ITEMS)

    def to_batch(self) -> HealthBatch:
        return HealthBatch(
            daily_summaries=[DailySummary(**s.model_dump()) for s in self.daily_summaries],
            samples=[HealthSample(**s.model_dump()) for s in self.samples],
            sleep_sessions=[SleepSession(**s.model_dump()) for s in self.sleep_sessions],
        )


class IngestResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    daily_summaries: int
    samples: int
    sleep_sessions: int


class DailySummaryRead(DailySummaryIn):
    model_config = ConfigDict(from_attributes=True)

    source: HealthSource


class HealthSampleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    metric: SampleMetric
    recorded_at: datetime
    value: float
    source: HealthSource


class SleepSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    start_at: datetime
    end_at: datetime
    deep_s: int | None
    light_s: int | None
    rem_s: int | None
    awake_s: int | None
    score: int | None
    source: HealthSource
