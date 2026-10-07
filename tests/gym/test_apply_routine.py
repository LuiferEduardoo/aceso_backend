from datetime import date

import pytest

from aceso.gym.application.apply_routine import ApplyRoutine
from aceso.gym.domain.entities import Routine, RoutineExercise
from aceso.shared.domain.errors import NotFoundError
from tests.gym.fakes import FakeRoutineRepository, FakeWorkoutSessionRepository


async def test_apply_routine_copies_exercises_and_prefills_sets() -> None:
    routines = FakeRoutineRepository()
    routine = await routines.add(
        Routine(
            user_id=1,
            name="Legs",
            exercises=[
                RoutineExercise(
                    exercise_id=10, position=1, target_sets=3, target_reps=5, target_weight_kg=100
                ),
                RoutineExercise(exercise_id=11, position=2, target_sets=2),  # no metrics
                RoutineExercise(exercise_id=12, position=3, target_sets=1, target_duration_s=600),
            ],
        )
    )
    assert routine.id
    use_case = ApplyRoutine(routines, FakeWorkoutSessionRepository())

    session = await use_case.execute(1, routine.id, date(2026, 10, 9))

    assert session.routine_id == routine.id
    assert session.scheduled_date == date(2026, 10, 9)
    assert [e.exercise_id for e in session.exercises] == [10, 11, 12]
    first = session.exercises[0].sets
    assert [(s.set_number, s.reps, s.weight_kg, s.completed) for s in first] == [
        (1, 5, 100, False),
        (2, 5, 100, False),
        (3, 5, 100, False),
    ]
    assert session.exercises[1].sets == []
    assert session.exercises[2].sets[0].duration_s == 600


async def test_apply_routine_of_other_user_fails() -> None:
    routines = FakeRoutineRepository()
    routine = await routines.add(Routine(user_id=2, name="Legs"))
    assert routine.id
    with pytest.raises(NotFoundError):
        await ApplyRoutine(routines, FakeWorkoutSessionRepository()).execute(
            1, routine.id, date(2026, 10, 9)
        )
