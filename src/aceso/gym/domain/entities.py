from dataclasses import dataclass
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
