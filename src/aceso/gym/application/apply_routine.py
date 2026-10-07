from datetime import date

from aceso.gym.domain.entities import (
    ExerciseSet,
    RoutineExercise,
    SessionExercise,
    WorkoutSession,
)
from aceso.gym.domain.ports import RoutineRepository, WorkoutSessionRepository
from aceso.shared.domain.errors import NotFoundError


def _planned_sets(item: RoutineExercise) -> list[ExerciseSet]:
    template = ExerciseSet(
        reps=item.target_reps,
        weight_kg=item.target_weight_kg,
        duration_s=item.target_duration_s,
    )
    if not item.target_sets or not template.has_metrics():
        return []
    return [
        ExerciseSet(
            set_number=number,
            reps=template.reps,
            weight_kg=template.weight_kg,
            duration_s=template.duration_s,
        )
        for number in range(1, item.target_sets + 1)
    ]


class ApplyRoutine:
    """Schedule a workout session on a date from a routine, pre-filling its target sets."""

    def __init__(self, routines: RoutineRepository, sessions: WorkoutSessionRepository) -> None:
        self._routines = routines
        self._sessions = sessions

    async def execute(
        self, user_id: int, routine_id: int, scheduled_date: date, notes: str | None = None
    ) -> WorkoutSession:
        routine = await self._routines.get(user_id, routine_id)
        if routine is None:
            raise NotFoundError("Routine not found")
        session = WorkoutSession(
            user_id=user_id,
            scheduled_date=scheduled_date,
            routine_id=routine.id,
            notes=notes,
            exercises=[
                SessionExercise(
                    exercise_id=item.exercise_id,
                    position=position,
                    notes=item.notes,
                    sets=_planned_sets(item),
                )
                for position, item in enumerate(routine.exercises, start=1)
            ],
        )
        return await self._sessions.add(session)
