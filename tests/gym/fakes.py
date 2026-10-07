from dataclasses import replace
from datetime import UTC, datetime

from aceso.gym.domain.entities import Exercise


class FakeExerciseRepository:
    def __init__(self) -> None:
        self.items: dict[int, Exercise] = {}
        self._next_id = 1

    async def add(self, exercise: Exercise) -> Exercise:
        exercise = replace(exercise, id=self._next_id, created_at=datetime.now(UTC))
        self.items[self._next_id] = exercise
        self._next_id += 1
        return replace(exercise)

    async def get(self, user_id: int, exercise_id: int) -> Exercise | None:
        exercise = self.items.get(exercise_id)
        return replace(exercise) if exercise and exercise.user_id == user_id else None

    async def list(self, user_id: int) -> list[Exercise]:
        return [replace(e) for e in self.items.values() if e.user_id == user_id]

    async def update(self, exercise: Exercise) -> Exercise:
        assert exercise.id is not None
        self.items[exercise.id] = replace(exercise)
        return replace(exercise)

    async def delete(self, exercise: Exercise) -> None:
        assert exercise.id is not None
        self.items.pop(exercise.id, None)


class FakeStorage:
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}

    async def save(self, key: str, content: bytes) -> None:
        self.files[key] = content

    async def read(self, key: str) -> bytes | None:
        return self.files.get(key)

    async def delete(self, key: str) -> None:
        self.files.pop(key, None)
