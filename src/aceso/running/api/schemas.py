from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from aceso.running.domain.entities import PlannedRun, RunType


class PlannedRunIn(BaseModel):
    scheduled_date: date
    run_type: RunType = RunType.EASY
    target_distance_m: float | None = Field(default=None, gt=0)
    target_duration_s: int | None = Field(default=None, gt=0)
    target_pace_s_per_km: int | None = Field(default=None, gt=0)
    description: str | None = None

    def to_entity(self) -> PlannedRun:
        return PlannedRun(**self.model_dump())


class PlannedRunUpdate(BaseModel):
    scheduled_date: date | None = None
    run_type: RunType | None = None
    target_distance_m: float | None = Field(default=None, gt=0)
    target_duration_s: int | None = Field(default=None, gt=0)
    target_pace_s_per_km: int | None = Field(default=None, gt=0)
    description: str | None = None


class PlannedRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plan_id: int
    scheduled_date: date
    run_type: RunType
    target_distance_m: float | None
    target_duration_s: int | None
    target_pace_s_per_km: int | None
    description: str | None


class TrainingPlanCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    goal: str | None = None
    start_date: date
    end_date: date
    runs: list[PlannedRunIn] = []


class TrainingPlanUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    goal: str | None = None
    start_date: date | None = None
    end_date: date | None = None


class TrainingPlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    goal: str | None
    start_date: date
    end_date: date
    runs: list[PlannedRunRead]
    created_at: datetime
