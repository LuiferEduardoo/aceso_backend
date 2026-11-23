from datetime import UTC, date, datetime, time, timedelta

import pytest

from aceso.planner.application.calendar import CalendarService
from aceso.planner.application.habits import HabitService
from aceso.planner.application.tasks import TaskService
from aceso.planner.domain.entities import CalendarEvent, Habit, HabitFrequency, Task
from tests.planner.google_mock import timed
from tests.planner.sync_harness import NOW, Harness

START = datetime(2026, 10, 12, 9, tzinfo=UTC)


@pytest.fixture
async def h() -> Harness:
    harness = Harness()
    await harness.connect()
    return harness


def _event(**kwargs: object) -> CalendarEvent:
    values: dict = {
        "user_id": 1,
        "title": "Physio",
        "start_at": START,
        "end_at": START + timedelta(hours=1),
    }
    values.update(kwargs)
    return CalendarEvent(**values)


async def test_push_insert_patch_and_delete(h: Harness) -> None:
    calendar = CalendarService(h.events, clock=lambda: NOW)
    event = await calendar.create(_event(location="Clinic"))
    assert event.id is not None

    await h.sync()
    assert (h.last.pushed, h.last.deleted) == (1, 0)
    stored = h.events.events[event.id]
    assert stored.google_event_id == "g1" and not stored.sync_pending
    remote = h.api.live()["g1"]
    assert remote["summary"] == "Physio" and remote["location"] == "Clinic"
    assert remote["start"] == {"dateTime": "2026-10-12T09:00:00+00:00", "timeZone": "UTC"}
    assert remote["extendedProperties"]["private"]["aceso_ref"] == f"event:{event.id}"

    await h.sync()  # our own change comes back in the delta and is recognised
    assert (h.last.pulled, h.last.pushed) == (0, 0)

    await calendar.update(1, event.id, {"title": "Physio (moved)"})
    await h.sync()
    assert h.last.pushed == 1 and h.api.live()["g1"]["summary"] == "Physio (moved)"

    await calendar.delete(1, event.id)
    await h.sync()
    assert h.last.deleted == 1
    assert h.api.live() == {} and h.events.events == {}


async def test_all_day_event_uses_dates(h: Harness) -> None:
    await CalendarService(h.events).create(_event(all_day=True, end_at=START + timedelta(days=1)))
    await h.sync()
    remote = h.api.live()["g1"]
    assert remote["start"] == {"date": "2026-10-12"} and remote["end"] == {"date": "2026-10-13"}


async def test_patch_of_vanished_remote_event_recreates_it(h: Harness) -> None:
    calendar = CalendarService(h.events)
    event = await calendar.create(_event())
    assert event.id is not None
    await h.sync()
    del h.api.events["me@example.com"]["g1"]  # vanished without a cancellation

    await calendar.update(1, event.id, {"title": "Again"})
    await h.sync()

    assert h.events.events[event.id].google_event_id == "g2"
    assert h.api.live()["g2"]["summary"] == "Again"


async def test_scheduled_task_is_pushed_and_tagged(h: Harness) -> None:
    task = await TaskService(h.tasks, h.events).create(
        Task(
            user_id=1,
            title="Dentist",
            scheduled_start=START,
            scheduled_end=START + timedelta(hours=1),
        )
    )
    await h.sync()
    remote = h.api.live()["g1"]
    assert remote["summary"] == "Dentist"
    assert remote["extendedProperties"]["private"]["aceso_ref"] == f"task:{task.id}"


async def test_habit_is_pushed_as_one_recurring_event(h: Harness) -> None:
    service = HabitService(h.habits, h.events, clock=lambda: NOW)
    habit = await service.create(
        Habit(
            user_id=1,
            name="Stretch",
            start_date=date(2026, 10, 12),
            frequency=HabitFrequency.WEEKDAYS,
            weekdays=[0, 3],
            time_of_day=time(7),
            duration_min=20,
            timezone="Europe/Madrid",
            sync_to_calendar=True,
        )
    )
    assert habit.id is not None
    await h.sync()

    [remote] = h.api.live().values()
    assert remote["recurrence"] == ["RRULE:FREQ=WEEKLY;BYDAY=MO,TH"]
    assert remote["start"] == {
        "dateTime": "2026-10-12T07:00:00+02:00",
        "timeZone": "Europe/Madrid",
    }
    assert remote["extendedProperties"]["private"]["aceso_ref"] == f"habit:{habit.id}"

    # Expanded instances coming back from Google are not imported as events.
    h.api.add_remote(
        "g1_20261015T050000Z",
        recurringEventId="g1",
        **timed("2026-10-15T05:00:00Z", "2026-10-15T05:20:00Z"),
    )
    await h.sync()
    assert len(h.events.events) == 1

    await service.update(1, habit.id, {"weekdays": [1]})
    await h.sync()
    assert h.api.live()["g1"]["recurrence"] == ["RRULE:FREQ=WEEKLY;BYDAY=TU"]

    await service.archive(1, habit.id)
    await h.sync()
    assert "g1" not in h.api.live() and h.events.events == {}


async def test_pushed_but_unrecorded_event_is_adopted_not_duplicated(h: Harness) -> None:
    event = await CalendarService(h.events).create(_event())
    # Google has it (a previous push whose local write was rolled back).
    h.api.add_remote(
        "lost",
        summary="Physio",
        extendedProperties={"private": {"aceso_ref": f"event:{event.id}"}},
        **timed("2026-10-12T09:00:00Z", "2026-10-12T10:00:00Z"),
    )

    await h.sync()

    assert list(h.api.live()) == ["lost"]
    assert [e.google_event_id for e in h.events.events.values()] == ["lost"]
