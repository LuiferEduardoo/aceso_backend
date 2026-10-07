from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class ExerciseCategory(StrEnum):
    STRENGTH = "strength"
    CARDIO = "cardio"
    BODYWEIGHT = "bodyweight"
    OTHER = "other"


@dataclass(slots=True)
class Exercise:
    user_id: int
    name: str
    category: ExerciseCategory = ExerciseCategory.STRENGTH
    notes: str | None = None
    photo_key: str | None = None
    id: int | None = None
    created_at: datetime | None = None


@dataclass(slots=True)
class RoutineExercise:
    exercise_id: int
    position: int = 0
    target_sets: int | None = None
    target_reps: int | None = None
    target_weight_kg: float | None = None
    target_duration_s: int | None = None
    notes: str | None = None
    id: int | None = None


@dataclass(slots=True)
class Routine:
    user_id: int
    name: str
    description: str | None = None
    exercises: list[RoutineExercise] = field(default_factory=list)
    id: int | None = None
    created_at: datetime | None = None
