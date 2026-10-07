from datetime import datetime

from pydantic import BaseModel, Field

from aceso.gym.domain.entities import Exercise, ExerciseCategory, Routine, RoutineExercise


class ExerciseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    category: ExerciseCategory = ExerciseCategory.STRENGTH
    notes: str | None = None


class ExerciseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    category: ExerciseCategory | None = None
    notes: str | None = None


class ExerciseRead(BaseModel):
    id: int
    name: str
    category: ExerciseCategory
    notes: str | None
    photo_url: str | None
    created_at: datetime

    @classmethod
    def from_entity(cls, exercise: Exercise) -> "ExerciseRead":
        assert exercise.id is not None and exercise.created_at is not None
        return cls(
            id=exercise.id,
            name=exercise.name,
            category=exercise.category,
            notes=exercise.notes,
            photo_url=f"/gym/exercises/{exercise.id}/photo" if exercise.photo_key else None,
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
