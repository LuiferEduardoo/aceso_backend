from datetime import date, datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aceso.gym.domain.entities import (
    Equipment,
    Exercise,
    ExerciseSet,
    ExerciseType,
    MuscleGroup,
    Routine,
    RoutineExercise,
    SessionExercise,
    SessionStatus,
    SetInterval,
)


class ExerciseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    muscle_group: MuscleGroup
    secondary_muscles: list[MuscleGroup] = Field(
        default=[], description="Other muscles worked; unique and without the primary muscle_group."
    )
    equipment: Equipment
    exercise_type: ExerciseType
    instructions: str | None = Field(default=None, description="Technique description.")


class ExerciseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    muscle_group: MuscleGroup | None = None
    secondary_muscles: list[MuscleGroup] | None = None
    equipment: Equipment | None = None
    exercise_type: ExerciseType | None = None
    instructions: str | None = None


class ExerciseRead(BaseModel):
    id: int
    name: str
    muscle_group: MuscleGroup
    secondary_muscles: list[MuscleGroup]
    equipment: Equipment
    exercise_type: ExerciseType
    instructions: str | None
    image_url: str | None
    created_at: datetime

    @classmethod
    def from_entity(cls, exercise: Exercise) -> "ExerciseRead":
        assert exercise.id is not None and exercise.created_at is not None
        return cls(
            id=exercise.id,
            name=exercise.name,
            muscle_group=exercise.muscle_group,
            secondary_muscles=list(exercise.secondary_muscles),
            equipment=exercise.equipment,
            exercise_type=exercise.exercise_type,
            instructions=exercise.instructions,
            image_url=f"/gym/exercises/{exercise.id}/photo" if exercise.photo_key else None,
            created_at=exercise.created_at,
        )


class RoutineExerciseIn(BaseModel):
    exercise_id: int = Field(ge=1)
    target_sets: int | None = Field(default=None, ge=1, le=100)
    target_reps: int | None = Field(default=None, ge=1, le=1000)
    target_weight_kg: float | None = Field(default=None, ge=0)
    target_duration_s: int | None = Field(default=None, gt=0)
    notes: str | None = None

    def to_entity(self) -> RoutineExercise:
        return RoutineExercise(**self.model_dump())


class RoutineExerciseRead(RoutineExerciseIn):
    id: int
    position: int


class RoutineCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    exercises: list[RoutineExerciseIn] = []


class RoutineUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    exercises: list[RoutineExerciseIn] | None = Field(
        default=None, description="When present, replaces the whole exercise list (in order)."
    )


class RoutineRead(BaseModel):
    id: int
    name: str
    description: str | None
    exercises: list[RoutineExerciseRead]
    created_at: datetime

    @classmethod
    def from_entity(cls, routine: Routine) -> "RoutineRead":
        assert routine.id is not None and routine.created_at is not None
        return cls(
            id=routine.id,
            name=routine.name,
            description=routine.description,
            created_at=routine.created_at,
            exercises=[
                RoutineExerciseRead(
                    id=item.id or 0,
                    position=item.position,
                    exercise_id=item.exercise_id,
                    target_sets=item.target_sets,
                    target_reps=item.target_reps,
                    target_weight_kg=item.target_weight_kg,
                    target_duration_s=item.target_duration_s,
                    notes=item.notes,
                )
                for item in routine.exercises
            ],
        )


class SetIntervalIn(BaseModel):
    duration_s: int | None = Field(default=None, gt=0)
    distance_m: float | None = Field(default=None, gt=0)
    speed: float | None = Field(default=None, ge=0, description="km/h (treadmill) or similar")
    incline_pct: float | None = Field(default=None, ge=-100, le=100)
    level: int | None = Field(default=None, ge=0, description="Machine level, e.g. stair climber")

    @model_validator(mode="after")
    def _has_length(self) -> Self:
        if self.duration_s is None and self.distance_m is None:
            raise ValueError("An interval needs duration_s or distance_m")
        return self

    def to_entity(self) -> SetInterval:
        return SetInterval(**self.model_dump())


class SetIntervalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    position: int
    duration_s: int | None
    distance_m: float | None
    speed: float | None
    incline_pct: float | None
    level: int | None


class ExerciseSetIn(BaseModel):
    reps: int | None = Field(default=None, ge=0)
    weight_kg: float | None = Field(default=None, ge=0)
    added_weight_kg: float | None = Field(
        default=None, ge=0, description="Extra load, e.g. a backpack during bodyweight work"
    )
    duration_s: int | None = Field(default=None, gt=0)
    distance_m: float | None = Field(default=None, ge=0)
    rpe: float | None = Field(default=None, ge=1, le=10)
    completed: bool = False
    notes: str | None = None
    intervals: list[SetIntervalIn] = []

    def to_entity(self) -> ExerciseSet:
        return ExerciseSet(
            **self.model_dump(exclude={"intervals"}),
            intervals=[i.to_entity() for i in self.intervals],
        )


class ExerciseSetUpdate(BaseModel):
    reps: int | None = Field(default=None, ge=0)
    weight_kg: float | None = Field(default=None, ge=0)
    added_weight_kg: float | None = Field(default=None, ge=0)
    duration_s: int | None = Field(default=None, gt=0)
    distance_m: float | None = Field(default=None, ge=0)
    rpe: float | None = Field(default=None, ge=1, le=10)
    completed: bool | None = None
    notes: str | None = None
    intervals: list[SetIntervalIn] | None = Field(
        default=None, description="When present, replaces all intervals of the set."
    )


class ExerciseSetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    set_number: int
    reps: int | None
    weight_kg: float | None
    added_weight_kg: float | None
    duration_s: int | None
    distance_m: float | None
    rpe: float | None
    completed: bool
    notes: str | None
    intervals: list[SetIntervalRead]


class SessionExerciseIn(BaseModel):
    exercise_id: int = Field(ge=1)
    notes: str | None = None
    sets: list[ExerciseSetIn] = []

    def to_entity(self) -> SessionExercise:
        return SessionExercise(
            exercise_id=self.exercise_id,
            notes=self.notes,
            sets=[s.to_entity() for s in self.sets],
        )


class SessionExerciseAdd(BaseModel):
    exercise_id: int = Field(ge=1)
    notes: str | None = None


class SessionExerciseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    exercise_id: int
    position: int
    notes: str | None
    sets: list[ExerciseSetRead]


class WorkoutSessionCreate(BaseModel):
    scheduled_date: date
    status: SessionStatus = SessionStatus.PLANNED
    started_at: datetime | None = None
    finished_at: datetime | None = None
    notes: str | None = None
    exercises: list[SessionExerciseIn] = []


class WorkoutSessionUpdate(BaseModel):
    scheduled_date: date | None = None
    status: SessionStatus | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    notes: str | None = None


class WorkoutSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    scheduled_date: date
    status: SessionStatus
    routine_id: int | None
    started_at: datetime | None
    finished_at: datetime | None
    notes: str | None
    exercises: list[SessionExerciseRead]
    created_at: datetime


class ApplyRoutineRequest(BaseModel):
    scheduled_date: date
    notes: str | None = None
