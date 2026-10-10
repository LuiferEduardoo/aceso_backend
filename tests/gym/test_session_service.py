from datetime import UTC, date, datetime

import pytest

from aceso.gym.application.sessions import WorkoutSessionService
from aceso.gym.domain.entities import (
    ExerciseSet,
    SessionStatus,
    SetInterval,
    WorkoutSession,
)
from aceso.shared.domain.errors import InvalidOperationError, NotFoundError
from tests.gym.factories import make_exercise
from tests.gym.fakes import FakeExerciseRepository, FakeWorkoutSessionRepository


@pytest.fixture
def exercises() -> FakeExerciseRepository:
    return FakeExerciseRepository()


@pytest.fixture
def service(exercises: FakeExerciseRepository) -> WorkoutSessionService:
    return WorkoutSessionService(FakeWorkoutSessionRepository(), exercises)


async def _session_with_exercise(
    service: WorkoutSessionService, exercises: FakeExerciseRepository
) -> int:
    exercise = await exercises.add(make_exercise(1, "Stair climber"))
    session = await service.create(WorkoutSession(user_id=1, scheduled_date=date(2026, 10, 7)))
    assert exercise.id and session.id
    item = await service.add_exercise(1, session.id, exercise.id)
    assert item.id
    return item.id


async def test_calendar_filters_by_range_and_validates(service: WorkoutSessionService) -> None:
    for day in (1, 10, 20):
        await service.create(WorkoutSession(user_id=1, scheduled_date=date(2026, 10, day)))
    await service.create(WorkoutSession(user_id=2, scheduled_date=date(2026, 10, 10)))

    sessions = await service.calendar(1, date(2026, 10, 5), date(2026, 10, 20))
    assert [s.scheduled_date.day for s in sessions] == [10, 20]

    with pytest.raises(InvalidOperationError):
        await service.calendar(1, date(2026, 10, 5), date(2026, 10, 1))
    with pytest.raises(InvalidOperationError):
        await service.calendar(1, date(2025, 1, 1), date(2026, 10, 1))


async def test_interval_set_derives_total_duration(
    service: WorkoutSessionService, exercises: FakeExerciseRepository
) -> None:
    item_id = await _session_with_exercise(service, exercises)
    exercise_set = await service.add_set(
        1,
        item_id,
        ExerciseSet(
            intervals=[SetInterval(duration_s=60, level=5), SetInterval(duration_s=60, level=10)]
        ),
    )
    assert exercise_set.set_number == 1
    assert exercise_set.duration_s == 120
    assert [i.position for i in exercise_set.intervals] == [1, 2]

    second = await service.add_set(1, item_id, ExerciseSet(reps=10, added_weight_kg=8))
    assert second.set_number == 2


async def test_set_requires_a_metric(
    service: WorkoutSessionService, exercises: FakeExerciseRepository
) -> None:
    item_id = await _session_with_exercise(service, exercises)
    with pytest.raises(InvalidOperationError):
        await service.add_set(1, item_id, ExerciseSet(rpe=7))


async def test_replacing_intervals_recomputes_duration(
    service: WorkoutSessionService, exercises: FakeExerciseRepository
) -> None:
    item_id = await _session_with_exercise(service, exercises)
    created = await service.add_set(
        1, item_id, ExerciseSet(intervals=[SetInterval(duration_s=60, speed=10)])
    )
    assert created.id
    updated = await service.update_set(
        1,
        created.id,
        {"completed": True},
        [SetInterval(duration_s=120, speed=8, incline_pct=5), SetInterval(duration_s=30)],
    )
    assert updated.duration_s == 150
    assert updated.completed is True


async def test_update_rejects_finish_before_start(service: WorkoutSessionService) -> None:
    session = await service.create(WorkoutSession(user_id=1, scheduled_date=date(2026, 10, 7)))
    assert session.id
    with pytest.raises(InvalidOperationError):
        await service.update(
            1,
            session.id,
            {
                "started_at": datetime(2026, 10, 7, 10, tzinfo=UTC),
                "finished_at": datetime(2026, 10, 7, 9, tzinfo=UTC),
            },
        )
    updated = await service.update(1, session.id, {"status": SessionStatus.COMPLETED})
    assert updated.status == SessionStatus.COMPLETED


async def test_cannot_touch_other_users_sets(
    service: WorkoutSessionService, exercises: FakeExerciseRepository
) -> None:
    item_id = await _session_with_exercise(service, exercises)
    created = await service.add_set(1, item_id, ExerciseSet(reps=5))
    assert created.id
    with pytest.raises(NotFoundError):
        await service.update_set(2, created.id, {"reps": 6})
    with pytest.raises(NotFoundError):
        await service.add_set(2, item_id, ExerciseSet(reps=5))
