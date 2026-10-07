from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime

from aceso.gym.domain.entities import Exercise, Routine


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

    async def list_all(self, user_id: int) -> list[Exercise]:
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


class FakeRoutineRepository:
    def __init__(self) -> None:
        self.items: dict[int, Routine] = {}
        self._next_id = 1

    async def add(self, routine: Routine) -> Routine:
        routine = deepcopy(routine)
        routine.id, routine.created_at = self._next_id, datetime.now(UTC)
        for index, item in enumerate(routine.exercises, start=1):
            item.id = index
        self.items[self._next_id] = routine
        self._next_id += 1
        return deepcopy(routine)

    async def get(self, user_id: int, routine_id: int) -> Routine | None:
        routine = self.items.get(routine_id)
        return deepcopy(routine) if routine and routine.user_id == user_id else None

    async def list_all(self, user_id: int) -> list[Routine]:
        return [deepcopy(r) for r in self.items.values() if r.user_id == user_id]

    async def update(self, routine: Routine) -> Routine:
        assert routine.id is not None
        self.items[routine.id] = deepcopy(routine)
        return deepcopy(routine)

    async def delete(self, routine: Routine) -> None:
        assert routine.id is not None
        self.items.pop(routine.id, None)
