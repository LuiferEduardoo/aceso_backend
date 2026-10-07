from datetime import date
from typing import Any

from aceso.gym.application.routines import ensure_exercises_owned
from aceso.gym.domain.entities import (
    ExerciseSet,
    SessionExercise,
    SetInterval,
    WorkoutSession,
)
from aceso.gym.domain.ports import ExerciseRepository, WorkoutSessionRepository
from aceso.shared.domain.errors import InvalidOperationError, NotFoundError

MAX_CALENDAR_RANGE_DAYS = 366
SESSION_FIELDS = {"scheduled_date", "status", "started_at", "finished_at", "notes"}
SET_FIELDS = {
    "reps",
    "weight_kg",
    "added_weight_kg",
    "duration_s",
    "distance_m",
    "rpe",
    "completed",
    "notes",
}


def _validate_times(session: WorkoutSession) -> None:
    if session.started_at and session.finished_at and session.finished_at < session.started_at:
        raise InvalidOperationError("finished_at must be after started_at")


def _prepare_set(exercise_set: ExerciseSet) -> ExerciseSet:
    exercise_set.normalize()
    if not exercise_set.has_metrics():
        raise InvalidOperationError(
            "A set needs at least one metric (reps, weight, duration, distance or intervals)"
        )
    return exercise_set


class WorkoutSessionService:
    def __init__(self, sessions: WorkoutSessionRepository, exercises: ExerciseRepository) -> None:
        self._sessions = sessions
        self._exercises = exercises

    async def create(self, session: WorkoutSession) -> WorkoutSession:
        _validate_times(session)
        await ensure_exercises_owned(
            self._exercises, session.user_id, {e.exercise_id for e in session.exercises}
        )
        for position, item in enumerate(session.exercises, start=1):
            item.position = position
            for number, exercise_set in enumerate(item.sets, start=1):
                exercise_set.set_number = number
                _prepare_set(exercise_set)
        return await self._sessions.add(session)

    async def calendar(self, user_id: int, start: date, end: date) -> list[WorkoutSession]:
        if end < start:
            raise InvalidOperationError("'to' must be on or after 'from'")
        if (end - start).days > MAX_CALENDAR_RANGE_DAYS:
            raise InvalidOperationError(f"Range cannot exceed {MAX_CALENDAR_RANGE_DAYS} days")
        return await self._sessions.list_range(user_id, start, end)

    async def get(self, user_id: int, session_id: int) -> WorkoutSession:
        session = await self._sessions.get(user_id, session_id)
        if session is None:
            raise NotFoundError("Workout session not found")
        return session

    async def update(
        self, user_id: int, session_id: int, changes: dict[str, Any]
    ) -> WorkoutSession:
        session = await self.get(user_id, session_id)
        for name, value in changes.items():
            if name in SESSION_FIELDS:
                setattr(session, name, value)
        _validate_times(session)
        await self._sessions.update(session)
        return await self.get(user_id, session_id)

    async def delete(self, user_id: int, session_id: int) -> None:
        await self._sessions.delete(await self.get(user_id, session_id))

    async def add_exercise(
        self, user_id: int, session_id: int, exercise_id: int, notes: str | None = None
    ) -> SessionExercise:
        session = await self.get(user_id, session_id)
        await ensure_exercises_owned(self._exercises, user_id, {exercise_id})
        position = max((e.position for e in session.exercises), default=0) + 1
        assert session.id is not None
        return await self._sessions.add_exercise(
            session.id, SessionExercise(exercise_id=exercise_id, position=position, notes=notes)
        )

    async def remove_exercise(self, user_id: int, session_exercise_id: int) -> None:
        await self._get_exercise(user_id, session_exercise_id)
        await self._sessions.delete_exercise(user_id, session_exercise_id)

    async def add_set(
        self, user_id: int, session_exercise_id: int, exercise_set: ExerciseSet
    ) -> ExerciseSet:
        item = await self._get_exercise(user_id, session_exercise_id)
        exercise_set.set_number = max((s.set_number for s in item.sets), default=0) + 1
        return await self._sessions.add_set(session_exercise_id, _prepare_set(exercise_set))

    async def update_set(
        self,
        user_id: int,
        set_id: int,
        changes: dict[str, Any],
        intervals: list[SetInterval] | None = None,
    ) -> ExerciseSet:
        exercise_set = await self._get_set(user_id, set_id)
        for name, value in changes.items():
            if name in SET_FIELDS:
                setattr(exercise_set, name, value)
        if intervals is not None:
            exercise_set.intervals = intervals
            # Totals derived from the old intervals must be recomputed from the new ones.
            for total in ("duration_s", "distance_m"):
                if total not in changes:
                    setattr(exercise_set, total, None)
        return await self._sessions.update_set(user_id, _prepare_set(exercise_set))

    async def delete_set(self, user_id: int, set_id: int) -> None:
        await self._get_set(user_id, set_id)
        await self._sessions.delete_set(user_id, set_id)

    async def _get_exercise(self, user_id: int, session_exercise_id: int) -> SessionExercise:
        item = await self._sessions.get_exercise(user_id, session_exercise_id)
        if item is None:
            raise NotFoundError("Session exercise not found")
        return item

    async def _get_set(self, user_id: int, set_id: int) -> ExerciseSet:
        exercise_set = await self._sessions.get_set(user_id, set_id)
        if exercise_set is None:
            raise NotFoundError("Set not found")
        return exercise_set
