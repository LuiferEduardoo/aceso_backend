from copy import deepcopy
from dataclasses import replace
from datetime import UTC, date, datetime

from aceso.gym.domain.entities import (
    Exercise,
    ExerciseSet,
    Routine,
    SessionExercise,
    WorkoutSession,
)


def _copy(exercise: Exercise) -> Exercise:
    return replace(exercise, secondary_muscles=list(exercise.secondary_muscles))


class FakeExerciseRepository:
    def __init__(self) -> None:
        self.items: dict[int, Exercise] = {}
        self._next_id = 1

    async def add(self, exercise: Exercise) -> Exercise:
        exercise = replace(_copy(exercise), id=self._next_id, created_at=datetime.now(UTC))
        self.items[self._next_id] = exercise
        self._next_id += 1
        return _copy(exercise)

    async def get(self, user_id: int, exercise_id: int) -> Exercise | None:
        exercise = self.items.get(exercise_id)
        return _copy(exercise) if exercise and exercise.user_id == user_id else None

    async def list_all(self, user_id: int) -> list[Exercise]:
        return [_copy(e) for e in self.items.values() if e.user_id == user_id]

    async def update(self, exercise: Exercise) -> Exercise:
        assert exercise.id is not None
        self.items[exercise.id] = _copy(exercise)
        return _copy(exercise)

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


class FakeWorkoutSessionRepository:
    def __init__(self) -> None:
        self.items: dict[int, WorkoutSession] = {}
        self._ids = {"session": 0, "exercise": 0, "set": 0}

    def _next(self, kind: str) -> int:
        self._ids[kind] += 1
        return self._ids[kind]

    def _assign_set_ids(self, item: SessionExercise) -> None:
        for exercise_set in item.sets:
            exercise_set.id = exercise_set.id or self._next("set")
            exercise_set.session_exercise_id = item.id

    async def add(self, session: WorkoutSession) -> WorkoutSession:
        session = deepcopy(session)
        session.id, session.created_at = self._next("session"), datetime.now(UTC)
        for item in session.exercises:
            item.id, item.session_id = self._next("exercise"), session.id
            self._assign_set_ids(item)
        self.items[session.id] = session
        return deepcopy(session)

    async def get(self, user_id: int, session_id: int) -> WorkoutSession | None:
        session = self.items.get(session_id)
        return deepcopy(session) if session and session.user_id == user_id else None

    async def list_range(self, user_id: int, start: date, end: date) -> list[WorkoutSession]:
        return [
            deepcopy(s)
            for s in sorted(self.items.values(), key=lambda s: s.scheduled_date)
            if s.user_id == user_id and start <= s.scheduled_date <= end
        ]

    async def update(self, session: WorkoutSession) -> WorkoutSession:
        assert session.id is not None
        stored = self.items[session.id]
        session = replace(deepcopy(session), exercises=stored.exercises)
        self.items[session.id] = session
        return deepcopy(session)

    async def delete(self, session: WorkoutSession) -> None:
        assert session.id is not None
        self.items.pop(session.id, None)

    async def add_exercise(self, session_id: int, item: SessionExercise) -> SessionExercise:
        item = deepcopy(item)
        item.id, item.session_id = self._next("exercise"), session_id
        self._assign_set_ids(item)
        self.items[session_id].exercises.append(item)
        return deepcopy(item)

    def _find_exercise(self, user_id: int, item_id: int) -> SessionExercise | None:
        for session in self.items.values():
            for item in session.exercises:
                if item.id == item_id and session.user_id == user_id:
                    return item
        return None

    async def get_exercise(self, user_id: int, session_exercise_id: int) -> SessionExercise | None:
        item = self._find_exercise(user_id, session_exercise_id)
        return deepcopy(item) if item else None

    async def delete_exercise(self, user_id: int, session_exercise_id: int) -> None:
        for session in self.items.values():
            session.exercises = [e for e in session.exercises if e.id != session_exercise_id]

    async def add_set(self, session_exercise_id: int, exercise_set: ExerciseSet) -> ExerciseSet:
        for session in self.items.values():
            for item in session.exercises:
                if item.id == session_exercise_id:
                    exercise_set = deepcopy(exercise_set)
                    exercise_set.id = self._next("set")
                    exercise_set.session_exercise_id = session_exercise_id
                    item.sets.append(exercise_set)
                    return deepcopy(exercise_set)
        raise AssertionError("session exercise not found")

    def _find_set(self, user_id: int, set_id: int) -> tuple[SessionExercise, int] | None:
        for session in self.items.values():
            if session.user_id != user_id:
                continue
            for item in session.exercises:
                for index, exercise_set in enumerate(item.sets):
                    if exercise_set.id == set_id:
                        return item, index
        return None

    async def get_set(self, user_id: int, set_id: int) -> ExerciseSet | None:
        found = self._find_set(user_id, set_id)
        return deepcopy(found[0].sets[found[1]]) if found else None

    async def update_set(self, user_id: int, exercise_set: ExerciseSet) -> ExerciseSet:
        assert exercise_set.id is not None
        found = self._find_set(user_id, exercise_set.id)
        assert found is not None
        found[0].sets[found[1]] = deepcopy(exercise_set)
        return deepcopy(exercise_set)

    async def delete_set(self, user_id: int, set_id: int) -> None:
        found = self._find_set(user_id, set_id)
        if found:
            found[0].sets.pop(found[1])
