from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum


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
