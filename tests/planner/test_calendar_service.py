from datetime import UTC, date, datetime, time, timedelta

import pytest

from aceso.planner.application.agenda import Agenda
from aceso.planner.application.calendar import CalendarService
from aceso.planner.application.habits import HabitService, HabitTracking
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
    assert event.start_at == datetime(2026, 10, 12, tzinfo=UTC)
    assert event.end_at == datetime(2026, 10, 13, tzinfo=UTC)
    assert event.sync_pending


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
    habit = await HabitService(habits).create(
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
