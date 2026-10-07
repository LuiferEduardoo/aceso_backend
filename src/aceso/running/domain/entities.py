from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import StrEnum
from typing import Any


class RunType(StrEnum):
    EASY = "easy"
    TEMPO = "tempo"
    INTERVAL = "interval"
    LONG = "long"
    RECOVERY = "recovery"
    RACE = "race"


@dataclass(slots=True)
class PlannedRun:
    scheduled_date: date
    run_type: RunType = RunType.EASY
    target_distance_m: float | None = None
    target_duration_s: int | None = None
    target_pace_s_per_km: int | None = None
    description: str | None = None
    plan_id: int | None = None
    id: int | None = None


@dataclass(slots=True)
class TrainingPlan:
    user_id: int
    name: str
    start_date: date
    end_date: date
    goal: str | None = None
    runs: list[PlannedRun] = field(default_factory=list)
    id: int | None = None
    created_at: datetime | None = None

    def covers(self, day: date) -> bool:
        return self.start_date <= day <= self.end_date


class ActivitySource(StrEnum):
    STRAVA = "strava"


@dataclass(slots=True)
class Activity:
    """A recorded workout imported from an external platform."""

    source: ActivitySource
    external_id: str
    sport_type: str
    start_at: datetime
    name: str | None = None
    distance_m: float | None = None
    moving_time_s: int | None = None
    elapsed_time_s: int | None = None
    elevation_gain_m: float | None = None
    avg_hr: float | None = None
    max_hr: float | None = None
    avg_speed: float | None = None
    calories: float | None = None
    raw: dict[str, Any] = field(default_factory=dict)
    user_id: int | None = None
    id: int | None = None


@dataclass(slots=True, frozen=True)
class OAuthTokens:
    access_token: str
    refresh_token: str
    expires_at: datetime
    athlete_id: int | None = None

    def expires_within(self, now: datetime, margin: timedelta) -> bool:
        return self.expires_at <= now + margin

    def to_payload(self) -> dict[str, Any]:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at.isoformat(),
            "athlete_id": self.athlete_id,
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "OAuthTokens":
        return cls(
            access_token=payload["access_token"],
            refresh_token=payload["refresh_token"],
            expires_at=datetime.fromisoformat(payload["expires_at"]),
            athlete_id=payload.get("athlete_id"),
        )
