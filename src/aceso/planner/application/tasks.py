from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Any

from aceso.planner.application.calendar import discard_event
from aceso.planner.domain.entities import CalendarEvent, Task, TaskStatus
from aceso.planner.domain.ports import CalendarEventRepository, TaskRepository
from aceso.shared.domain.errors import InvalidOperationError, NotFoundError

TASK_FIELDS = {
    "title",
    "notes",
    "status",
    "priority",
    "due_date",
    "scheduled_start",
    "scheduled_end",
}


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _validate_schedule(task: Task) -> None:
    if (task.scheduled_start is None) != (task.scheduled_end is None):
        raise InvalidOperationError("scheduled_start and scheduled_end go together")
    if task.scheduled_start and task.scheduled_end and task.scheduled_end <= task.scheduled_start:
        raise InvalidOperationError("scheduled_end must be after scheduled_start")


class TaskService:
    """Task CRUD; a scheduled task owns a linked calendar event kept in step with it."""

    def __init__(
        self,
        tasks: TaskRepository,
        events: CalendarEventRepository,
        clock: Callable[[], datetime] = _utcnow,
    ) -> None:
        self._tasks = tasks
        self._events = events
        self._clock = clock

    def _sync_completion(self, task: Task) -> None:
        if task.status == TaskStatus.DONE:
            task.completed_at = task.completed_at or self._clock()
        else:
            task.completed_at = None

    async def create(self, task: Task) -> Task:
        _validate_schedule(task)
        self._sync_completion(task)
        task = await self._tasks.add(task)
        await self._sync_event(task)
        return task

    async def list_filtered(
        self,
        user_id: int,
        status: TaskStatus | None = None,
        due_from: date | None = None,
        due_to: date | None = None,
    ) -> list[Task]:
        if due_from and due_to and due_to < due_from:
            raise InvalidOperationError("'due_to' must be on or after 'due_from'")
        return await self._tasks.list_filtered(user_id, status, due_from, due_to)

    async def get(self, user_id: int, task_id: int) -> Task:
        task = await self._tasks.get(user_id, task_id)
        if task is None:
            raise NotFoundError("Task not found")
        return task

    async def update(self, user_id: int, task_id: int, changes: dict[str, Any]) -> Task:
        task = await self.get(user_id, task_id)
        for name, value in changes.items():
            if name in TASK_FIELDS:
                setattr(task, name, value)
        _validate_schedule(task)
        self._sync_completion(task)
        task = await self._tasks.update(task)
        await self._sync_event(task)
        return task

    async def complete(self, user_id: int, task_id: int) -> Task:
        return await self.update(user_id, task_id, {"status": TaskStatus.DONE})

    async def reopen(self, user_id: int, task_id: int) -> Task:
        return await self.update(user_id, task_id, {"status": TaskStatus.TODO})

    async def delete(self, user_id: int, task_id: int) -> None:
        task = await self.get(user_id, task_id)
        assert task.id is not None
        event = await self._events.get_by_task(user_id, task.id)
        if event is not None:
            await discard_event(self._events, event, self._clock())
        await self._tasks.delete(task)

    async def _sync_event(self, task: Task) -> None:
        assert task.id is not None
        event = await self._events.get_by_task(task.user_id, task.id)
        if not task.is_scheduled:
            if event is not None:
                await discard_event(self._events, event, self._clock())
            return
        assert task.scheduled_start is not None and task.scheduled_end is not None
        wanted = {
            "title": task.title,
            "description": task.notes,
            "start_at": task.scheduled_start,
            "end_at": task.scheduled_end,
        }
        if event is None:
            await self._events.add(
                CalendarEvent(user_id=task.user_id, task_id=task.id, sync_pending=True, **wanted)
            )
        elif any(getattr(event, k) != v for k, v in wanted.items()):
            for name, value in wanted.items():
                setattr(event, name, value)
            event.sync_pending = True
            await self._events.update(event)
