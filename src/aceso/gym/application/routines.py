from aceso.gym.domain.entities import Routine, RoutineExercise
from aceso.gym.domain.ports import ExerciseRepository, RoutineRepository
from aceso.shared.domain.errors import NotFoundError


async def ensure_exercises_owned(
    exercises: ExerciseRepository, user_id: int, exercise_ids: set[int]
) -> None:
    for exercise_id in sorted(exercise_ids):
        if await exercises.get(user_id, exercise_id) is None:
            raise NotFoundError(f"Exercise {exercise_id} not found")


def _with_positions(items: list[RoutineExercise]) -> list[RoutineExercise]:
    for position, item in enumerate(items, start=1):
        item.position = position
    return items


class RoutineService:
    def __init__(self, routines: RoutineRepository, exercises: ExerciseRepository) -> None:
        self._routines = routines
        self._exercises = exercises

    async def create(self, routine: Routine) -> Routine:
        await ensure_exercises_owned(
            self._exercises, routine.user_id, {e.exercise_id for e in routine.exercises}
        )
        routine.exercises = _with_positions(routine.exercises)
        return await self._routines.add(routine)

    async def list_all(self, user_id: int) -> list[Routine]:
        return await self._routines.list_all(user_id)

    async def get(self, user_id: int, routine_id: int) -> Routine:
        routine = await self._routines.get(user_id, routine_id)
        if routine is None:
            raise NotFoundError("Routine not found")
        return routine

    async def update(
        self,
        user_id: int,
        routine_id: int,
        *,
        name: str | None = None,
        description: str | None = None,
        clear_description: bool = False,
        exercises: list[RoutineExercise] | None = None,
    ) -> Routine:
        routine = await self.get(user_id, routine_id)
        if name is not None:
            routine.name = name
        if description is not None or clear_description:
            routine.description = description
        if exercises is not None:
            await ensure_exercises_owned(
                self._exercises, user_id, {e.exercise_id for e in exercises}
            )
            routine.exercises = _with_positions(exercises)
        return await self._routines.update(routine)

    async def delete(self, user_id: int, routine_id: int) -> None:
        await self._routines.delete(await self.get(user_id, routine_id))
