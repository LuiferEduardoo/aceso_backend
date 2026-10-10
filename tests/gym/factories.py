from typing import Any

from aceso.gym.domain.entities import Equipment, Exercise, ExerciseType, MuscleGroup


def make_exercise(user_id: int, name: str, **overrides: Any) -> Exercise:
    fields: dict[str, Any] = {
        "muscle_group": MuscleGroup.QUADRICEPS,
        "equipment": Equipment.BARBELL,
        "exercise_type": ExerciseType.COMPOUND,
    }
    return Exercise(user_id=user_id, name=name, **(fields | overrides))


def exercise_payload(name: str, **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": name,
        "muscle_group": "quadriceps",
        "equipment": "barbell",
        "exercise_type": "compound",
    }
    return payload | overrides
