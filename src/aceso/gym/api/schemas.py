from datetime import datetime

from pydantic import BaseModel, Field

from aceso.gym.domain.entities import Exercise, ExerciseCategory


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
