import pytest

from aceso.gym.application.routines import RoutineService
from aceso.gym.domain.entities import Routine, RoutineExercise
from aceso.shared.domain.errors import NotFoundError
from tests.gym.factories import make_exercise
from tests.gym.fakes import FakeExerciseRepository, FakeRoutineRepository


@pytest.fixture
def exercises() -> FakeExerciseRepository:
    return FakeExerciseRepository()


@pytest.fixture
def service(exercises: FakeExerciseRepository) -> RoutineService:
    return RoutineService(FakeRoutineRepository(), exercises)


async def test_create_assigns_positions_in_order(
    service: RoutineService, exercises: FakeExerciseRepository
) -> None:
    squat = await exercises.add(make_exercise(1, "Squat"))
    bench = await exercises.add(make_exercise(1, "Bench"))
    assert squat.id and bench.id
    routine = await service.create(
        Routine(
            user_id=1,
            name="Leg day",
            exercises=[
                RoutineExercise(exercise_id=bench.id, target_sets=3),
                RoutineExercise(exercise_id=squat.id, target_sets=5),
            ],
        )
    )
    assert [(e.position, e.exercise_id) for e in routine.exercises] == [
        (1, bench.id),
        (2, squat.id),
    ]


async def test_create_rejects_exercises_of_other_users(
    service: RoutineService, exercises: FakeExerciseRepository
) -> None:
    foreign = await exercises.add(make_exercise(2, "Squat"))
    assert foreign.id
    with pytest.raises(NotFoundError):
        await service.create(
            Routine(user_id=1, name="R", exercises=[RoutineExercise(exercise_id=foreign.id)])
        )


async def test_update_replaces_exercises_and_keeps_name(
    service: RoutineService, exercises: FakeExerciseRepository
) -> None:
    squat = await exercises.add(make_exercise(1, "Squat"))
    assert squat.id
    routine = await service.create(Routine(user_id=1, name="Legs", description="old"))
    assert routine.id
    updated = await service.update(
        1,
        routine.id,
        clear_description=True,
        exercises=[RoutineExercise(exercise_id=squat.id, target_reps=8)],
    )
    assert updated.name == "Legs"
    assert updated.description is None
    assert [e.target_reps for e in updated.exercises] == [8]
