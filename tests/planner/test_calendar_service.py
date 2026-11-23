from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from aceso.planner.application.agenda import Agenda
from aceso.planner.application.calendar import CalendarService
from aceso.planner.application.habits import HabitService, HabitTracking
from aceso.planner.application.ranges import day_bounds
from aceso.planner.application.tasks import TaskService
from aceso.planner.domain.entities import CalendarEvent, Habit, HabitFrequency, Task
from aceso.shared.domain.errors import InvalidOperationError, NotFoundError
from tests.planner.fakes import (
    FakeCalendarEventRepository,
    FakeHabitRepository,
    FakeTaskRepository,
)

NOW = datetime(2026, 10, 10, 12, tzinfo=UTC)


def _at(day: int, hour: int = 9) -> datetime:
    return datetime(2026, 10, day, hour, tzinfo=UTC)


def _event(**kwargs: object) -> CalendarEvent:
    values: dict = {"user_id": 1, "title": "Meeting", "start_at": _at(12), "end_at": _at(12, 10)}
    values.update(kwargs)
    return CalendarEvent(**values)


@pytest.fixture
def events() -> FakeCalendarEventRepository:
    return FakeCalendarEventRepository()


async def test_event_times_and_all_day_normalization(events: FakeCalendarEventRepository) -> None:
    service = CalendarService(events)
    with pytest.raises(InvalidOperationError):
        await service.create(_event(end_at=_at(12, 8)))

    event = await service.create(_event(all_day=True, start_at=_at(12, 15), end_at=_at(12, 16)))
    assert event.start_at == datetime(2026, 10, 12, 5, tzinfo=UTC)  # Bogota midnight
    assert event.end_at == datetime(2026, 10, 13, 5, tzinfo=UTC)
    assert event.sync_pending

    # 02:00Z on the 12th is still the 11th in Bogota.
    late = await service.create(_event(all_day=True, start_at=_at(12, 2), end_at=_at(12, 3)))
    assert (late.start_at, late.end_at) == (_at(11, 5), _at(12, 5))


def test_day_bounds_follow_bogota_midnight() -> None:
    assert day_bounds(date(2026, 3, 10), date(2026, 3, 10)) == (
        datetime(2026, 3, 10, 5, tzinfo=UTC),
        datetime(2026, 3, 11, 5, tzinfo=UTC),
    )
    utc = ZoneInfo("UTC")
    assert day_bounds(date(2026, 3, 10), date(2026, 3, 10), utc) == (
        datetime(2026, 3, 10, tzinfo=utc),
        datetime(2026, 3, 11, tzinfo=utc),
    )


async def test_events_range_covers_one_bogota_day(events: FakeCalendarEventRepository) -> None:
    service = CalendarService(events)
    before = await service.create(_event(start_at=_at(12, 4), end_at=_at(12, 5)))  # 11th 23:00
    inside = await service.create(_event(start_at=_at(12, 5), end_at=_at(12, 6)))  # 12th 00:00
    last = await service.create(_event(start_at=_at(13, 4), end_at=_at(13, 5)))  # 12th 23:00
    after = await service.create(_event(start_at=_at(13, 5), end_at=_at(13, 6)))  # 13th 00:00
    found = {e.id for e in await service.between(1, date(2026, 10, 12), date(2026, 10, 12))}
    assert found == {inside.id, last.id}
    assert before.id not in found and after.id not in found


async def test_agenda_buckets_tasks_by_bogota_day(events: FakeCalendarEventRepository) -> None:
    tasks = FakeTaskRepository()
    late = datetime(2026, 3, 10, 22, tzinfo=ZoneInfo("America/Bogota"))  # 03:00Z on the 11th
    await TaskService(tasks, events).create(
        Task(user_id=1, title="Late", scheduled_start=late, scheduled_end=late + timedelta(hours=1))
    )
    tenth, eleventh = await Agenda(events, tasks, FakeHabitRepository()).between(
        1, date(2026, 3, 10), date(2026, 3, 11)
    )
    assert [t.title for t in tenth.tasks] == ["Late"]
    assert [e.title for e in tenth.events] == ["Late"]
    assert eleventh.tasks == [] and eleventh.events == []


async def test_range_and_delete(events: FakeCalendarEventRepository) -> None:
    service = CalendarService(events, clock=lambda: NOW)
    local = await service.create(_event())
    pushed = await service.create(_event(start_at=_at(13), end_at=_at(13, 10)))
    assert local.id is not None and pushed.id is not None
    pushed.google_event_id = "g1"
    await events.update(pushed)

    assert len(await service.between(1, date(2026, 10, 12), date(2026, 10, 13))) == 2
    assert [e.id for e in await service.between(1, date(2026, 10, 13), date(2026, 10, 13))] == [
        pushed.id
    ]
    with pytest.raises(InvalidOperationError):
        await service.between(1, date(2026, 10, 13), date(2026, 10, 12))

    await service.delete(1, local.id)
    assert local.id not in events.events
    await service.delete(1, pushed.id)
    assert events.events[pushed.id].deleted_at == NOW
    with pytest.raises(NotFoundError):
        await service.get(1, pushed.id)


async def test_linked_events_are_read_only(events: FakeCalendarEventRepository) -> None:
    service = CalendarService(events)
    event = await events.add(_event(task_id=5))
    assert event.id is not None
    with pytest.raises(InvalidOperationError):
        await service.update(1, event.id, {"title": "x"})
    with pytest.raises(InvalidOperationError):
        await service.delete(1, event.id)
    with pytest.raises(NotFoundError):
        await service.get(2, event.id)


async def test_agenda_merges_events_tasks_and_habits(events: FakeCalendarEventRepository) -> None:
    tasks, habits = FakeTaskRepository(), FakeHabitRepository()
    await CalendarService(events).create(_event(start_at=_at(12), end_at=_at(13, 10)))
    await events.add(_event(habit_id=1, title="Habit event"))
    task_service = TaskService(tasks, events)
    await task_service.create(Task(user_id=1, title="Due", due_date=date(2026, 10, 13)))
    await task_service.create(
        Task(user_id=1, title="Slot", scheduled_start=_at(12, 14), scheduled_end=_at(12, 15))
    )
    habit = await HabitService(habits, events).create(
        Habit(
            user_id=1,
            name="Gym",
            start_date=date(2026, 10, 1),
            frequency=HabitFrequency.WEEKDAYS,
            weekdays=[0],  # Mondays: 2026-10-12
            time_of_day=time(7),
        )
    )
    assert habit.id is not None
    await HabitTracking(habits).log(1, habit.id, date(2026, 10, 12))

    days = await Agenda(events, tasks, habits).between(1, date(2026, 10, 12), date(2026, 10, 13))

    monday, tuesday = days
    assert [e.title for e in monday.events] == ["Meeting", "Slot"]
    assert [t.title for t in monday.tasks] == ["Slot"]
    assert [(o.habit.name, o.count, o.completed) for o in monday.habits] == [("Gym", 1, True)]
    assert [e.title for e in tuesday.events] == ["Meeting"]  # multi-day event spans both
    assert [t.title for t in tuesday.tasks] == ["Due"]
    assert tuesday.habits == []
    assert monday.day + timedelta(days=1) == tuesday.day
