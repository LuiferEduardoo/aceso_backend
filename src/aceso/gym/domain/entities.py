from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum


class MuscleGroup(StrEnum):
    CHEST = "chest"
    BACK = "back"
    SHOULDERS = "shoulders"
    BICEPS = "biceps"
    TRICEPS = "triceps"
    FOREARMS = "forearms"
    ABS = "abs"
    QUADRICEPS = "quadriceps"
    HAMSTRINGS = "hamstrings"
    GLUTES = "glutes"
    CALVES = "calves"
    FULL_BODY = "full_body"
    CARDIO = "cardio"


class Equipment(StrEnum):
    BARBELL = "barbell"
    DUMBBELL = "dumbbell"
    MACHINE = "machine"
    CABLE = "cable"
    KETTLEBELL = "kettlebell"
    BODYWEIGHT = "bodyweight"
    BAND = "band"
    CARDIO_MACHINE = "cardio_machine"
    OTHER = "other"


class ExerciseType(StrEnum):
    COMPOUND = "compound"
    ISOLATION = "isolation"
    CARDIO = "cardio"


@dataclass(slots=True)
class Exercise:
    user_id: int
    name: str
    muscle_group: MuscleGroup
    equipment: Equipment
    exercise_type: ExerciseType
    secondary_muscles: list[MuscleGroup] = field(default_factory=list)
    instructions: str | None = None
    photo_key: str | None = None
    id: int | None = None
    created_at: datetime | None = None

    def muscle_errors(self) -> list[str]:
        """Return why the secondary muscles are inconsistent with the primary one (if they are)."""
        errors: list[str] = []
        if len(set(self.secondary_muscles)) != len(self.secondary_muscles):
            errors.append("secondary_muscles must not contain duplicates")
        if self.muscle_group in self.secondary_muscles:
            errors.append("secondary_muscles must not include the primary muscle_group")
        return errors


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


class SessionStatus(StrEnum):
    PLANNED = "planned"
    COMPLETED = "completed"
    SKIPPED = "skipped"


@dataclass(slots=True)
class SetInterval:
    """One segment of a set, e.g. 1 min at level 5 on a stair climber or 2 min at 10 km/h."""

    duration_s: int | None = None
    distance_m: float | None = None
    speed: float | None = None
    incline_pct: float | None = None
    level: int | None = None
    position: int = 0


@dataclass(slots=True)
class ExerciseSet:
    set_number: int = 0
    reps: int | None = None
    weight_kg: float | None = None
    added_weight_kg: float | None = None
    duration_s: int | None = None
    distance_m: float | None = None
    rpe: float | None = None
    completed: bool = False
    notes: str | None = None
    intervals: list[SetInterval] = field(default_factory=list)
    id: int | None = None
    session_exercise_id: int | None = None

    def has_metrics(self) -> bool:
        metrics = (
            self.reps,
            self.weight_kg,
            self.added_weight_kg,
            self.duration_s,
            self.distance_m,
        )
        return any(value is not None for value in metrics)

    def normalize(self) -> None:
        """Number the intervals and derive totals (duration/distance) from them when missing."""
        for position, interval in enumerate(self.intervals, start=1):
            interval.position = position
        if not self.intervals:
            return
        durations = [i.duration_s for i in self.intervals]
        if self.duration_s is None and all(d is not None for d in durations):
            self.duration_s = sum(d for d in durations if d is not None)
        distances = [i.distance_m for i in self.intervals]
        if self.distance_m is None and all(d is not None for d in distances):
            self.distance_m = sum(d for d in distances if d is not None)


@dataclass(slots=True)
class SessionExercise:
    exercise_id: int
    position: int = 0
    notes: str | None = None
    sets: list[ExerciseSet] = field(default_factory=list)
    id: int | None = None
    session_id: int | None = None


@dataclass(slots=True)
class WorkoutSession:
    """A workout on the calendar: planned for a date, then completed or skipped."""

    user_id: int
    scheduled_date: date
    status: SessionStatus = SessionStatus.PLANNED
    routine_id: int | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    notes: str | None = None
    exercises: list[SessionExercise] = field(default_factory=list)
    id: int | None = None
    created_at: datetime | None = None
