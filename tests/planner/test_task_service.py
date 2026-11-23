from datetime import UTC, date, datetime

import pytest

from aceso.planner.application.tasks import TaskService
from aceso.planner.domain.entities import Task, TaskStatus
from aceso.shared.domain.errors import InvalidOperationError, NotFoundError
from tests.planner.fakes import FakeCalendarEventRepository, FakeTaskRepository

NOW = datetime(2026, 10, 10, 12, tzinfo=UTC)


@pytest.fixture
def service() -> TaskService:
    return TaskService(FakeTaskRepository(), FakeCalendarEventRepository(), clock=lambda: NOW)


async def test_schedule_is_validated(service: TaskService) -> None:
    start = datetime(2026, 10, 11, 9, tzinfo=UTC)
    with pytest.raises(InvalidOperationError):
        await service.create(Task(user_id=1, title="x", scheduled_start=start))
    with pytest.raises(InvalidOperationError):
        await service.create(Task(user_id=1, title="x", scheduled_start=start, scheduled_end=start))


async def test_complete_and_reopen_track_completed_at(service: TaskService) -> None:
    task = await service.create(Task(user_id=1, title="Pay rent", due_date=date(2026, 10, 15)))
    assert task.id is not None and task.completed_at is None

    done = await service.complete(1, task.id)
    assert done.status == TaskStatus.DONE and done.completed_at == NOW

    reopened = await service.reopen(1, task.id)
    assert reopened.status == TaskStatus.TODO and reopened.completed_at is None

    created_done = await service.create(Task(user_id=1, title="x", status=TaskStatus.DONE))
    assert created_done.completed_at == NOW


async def test_filters_and_scoping(service: TaskService) -> None:
    await service.create(Task(user_id=1, title="a", due_date=date(2026, 10, 1)))
    await service.create(Task(user_id=1, title="b", due_date=date(2026, 10, 20)))
    other = await service.create(Task(user_id=2, title="c", due_date=date(2026, 10, 1)))
    assert other.id is not None

    found = await service.list_filtered(1, due_from=date(2026, 10, 10))
    assert [t.title for t in found] == ["b"]
    with pytest.raises(InvalidOperationError):
        await service.list_filtered(1, due_from=date(2026, 10, 10), due_to=date(2026, 10, 1))
    with pytest.raises(NotFoundError):
        await service.complete(1, other.id)


async def test_scheduled_task_keeps_a_linked_event() -> None:
    events = FakeCalendarEventRepository()
    service = TaskService(FakeTaskRepository(), events, clock=lambda: NOW)
    start = datetime(2026, 10, 11, 9, tzinfo=UTC)
    end = datetime(2026, 10, 11, 10, tzinfo=UTC)

    task = await service.create(
        Task(user_id=1, title="Dentist", scheduled_start=start, scheduled_end=end)
    )
    assert task.id is not None
    [event] = events.live(1)
    assert (event.task_id, event.title, event.start_at, event.sync_pending) == (
        task.id,
        "Dentist",
        start,
        True,
    )

    # Pretend it was pushed to Google, then reschedule: the same event is updated.
    event.google_event_id, event.sync_pending = "g1", False
    await events.update(event)
    later = datetime(2026, 10, 11, 15, tzinfo=UTC)
    await service.update(
        1, task.id, {"scheduled_start": later, "scheduled_end": end.replace(hour=16)}
    )
    [event] = events.live(1)
    assert event.start_at == later and event.sync_pending

    # A status change that does not touch the schedule leaves the event alone.
    event.sync_pending = False
    await events.update(event)
    await service.complete(1, task.id)
    assert not events.live(1)[0].sync_pending

    # Unscheduling turns a pushed event into a tombstone for the next push.
    await service.update(1, task.id, {"scheduled_start": None, "scheduled_end": None})
    assert events.live(1) == []
    [tombstone] = events.events.values()
    assert tombstone.deleted_at == NOW and tombstone.sync_pending


async def test_deleting_a_task_drops_its_unpushed_event() -> None:
    events = FakeCalendarEventRepository()
    service = TaskService(FakeTaskRepository(), events, clock=lambda: NOW)
    start = datetime(2026, 10, 11, 9, tzinfo=UTC)
    task = await service.create(
        Task(user_id=1, title="x", scheduled_start=start, scheduled_end=start.replace(hour=10))
    )
    assert task.id is not None
    await service.delete(1, task.id)
    assert events.events == {}
