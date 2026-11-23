from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

import pytest

from aceso.planner.application.habits import HabitService, HabitTracking
from aceso.planner.domain.entities import Habit, HabitFrequency
from aceso.shared.domain.errors import InvalidOperationError, NotFoundError
from tests.planner.fakes import FakeCalendarEventRepository, FakeHabitRepository

NOW = datetime(2026, 10, 10, 12, tzinfo=UTC)


def _habit(**kwargs: object) -> Habit:
    values: dict = {"user_id": 1, "name": "Read", "start_date": date(2026, 10, 5)}
    values.update(kwargs)
    return Habit(**values)


@pytest.fixture
def repo() -> FakeHabitRepository:
    return FakeHabitRepository()


async def test_frequency_rules_are_validated(repo: FakeHabitRepository) -> None:
    service = HabitService(repo, FakeCalendarEventRepository())
    with pytest.raises(InvalidOperationError):
        await service.create(_habit(frequency=HabitFrequency.WEEKDAYS))
    with pytest.raises(InvalidOperationError):
        await service.create(_habit(frequency=HabitFrequency.TIMES_PER_WEEK))
    with pytest.raises(InvalidOperationError):
        await service.create(_habit(timezone="Mars/Olympus"))
    with pytest.raises(InvalidOperationError):
        await service.create(_habit(sync_to_calendar=True))

    habit = await service.create(
        _habit(frequency=HabitFrequency.WEEKDAYS, weekdays=[4, 0, 4], times_per_week=3)
    )
    assert habit.weekdays == [0, 4] and habit.times_per_week is None

    habit = await service.create(_habit(sync_to_calendar=True, time_of_day=time(7)))
    assert habit.sync_to_calendar


async def test_archive_and_scoping(repo: FakeHabitRepository) -> None:
    service = HabitService(repo, FakeCalendarEventRepository(), clock=lambda: NOW)
    habit = await service.create(_habit())
    assert habit.id is not None

    archived = await service.archive(1, habit.id)
    assert archived.archived_at == NOW
    assert await service.list_all(1) == []
    assert len(await service.list_all(1, include_archived=True)) == 1
    assert (await service.unarchive(1, habit.id)).archived_at is None

    with pytest.raises(NotFoundError):
        await service.get(2, habit.id)


async def test_log_unlog_and_stats(repo: FakeHabitRepository) -> None:
    habit = await HabitService(repo, FakeCalendarEventRepository()).create(_habit())
    assert habit.id is not None
    tracking = HabitTracking(repo, clock=lambda: NOW)

    await tracking.log(1, habit.id, date(2026, 10, 8))
    await tracking.log(1, habit.id, date(2026, 10, 9), count=2, note="two chapters")
    log = await tracking.log(1, habit.id, date(2026, 10, 9), count=1)
    assert log.count == 1 and len(repo.logs) == 2

    stats = await tracking.stats(1, habit.id, date(2026, 10, 5), date(2026, 10, 10))
    assert stats.current_streak == 2
    assert (stats.completed, stats.expected) == (2, 6)

    await tracking.unlog(1, habit.id, date(2026, 10, 8))
    with pytest.raises(NotFoundError):
        await tracking.unlog(1, habit.id, date(2026, 10, 8))
    with pytest.raises(InvalidOperationError):
        await tracking.log(1, habit.id, date(2026, 10, 1))
    with pytest.raises(NotFoundError):
        await tracking.log(2, habit.id, date(2026, 10, 8))
    with pytest.raises(InvalidOperationError):
        await tracking.stats(1, habit.id, date(2026, 10, 5), date(2026, 10, 1))


async def test_archived_habits_cannot_be_logged(repo: FakeHabitRepository) -> None:
    service = HabitService(repo, FakeCalendarEventRepository(), clock=lambda: NOW)
    habit = await service.create(_habit())
    assert habit.id is not None
    await service.archive(1, habit.id)
    with pytest.raises(InvalidOperationError):
        await HabitTracking(repo).log(1, habit.id, date(2026, 10, 8))


async def test_stats_today_is_the_bogota_day(repo: FakeHabitRepository) -> None:
    habit = await HabitService(repo, FakeCalendarEventRepository()).create(_habit())
    assert habit.id is not None
    late_evening = datetime(2026, 10, 11, 3, tzinfo=UTC)  # 2026-10-10 22:00 in Bogota
    tracking = HabitTracking(repo, clock=lambda: late_evening)
    for day in (8, 9, 10):
        await tracking.log(1, habit.id, date(2026, 10, day))

    stats = await tracking.stats(1, habit.id, date(2026, 10, 5), date(2026, 10, 11))
    assert stats.current_streak == 3
    assert stats.expected == 6  # Oct 5..10: the 11th has not started in Bogota

    utc_tracking = HabitTracking(repo, clock=lambda: late_evening, tz=ZoneInfo("UTC"))
    utc_stats = await utc_tracking.stats(1, habit.id, date(2026, 10, 5), date(2026, 10, 11))
    assert utc_stats.expected == 7
