from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Any

from aceso.planner.domain.entities import Task, TaskStatus
from aceso.planner.domain.ports import TaskRepository
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
    def __init__(self, tasks: TaskRepository, clock: Callable[[], datetime] = _utcnow) -> None:
        self._tasks = tasks
        self._clock = clock

    def _sync_completion(self, task: Task) -> None:
        if task.status == TaskStatus.DONE:
            task.completed_at = task.completed_at or self._clock()
        else:
            task.completed_at = None

    async def create(self, task: Task) -> Task:
        _validate_schedule(task)
        self._sync_completion(task)
        return await self._save(task, created=True)

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
        return await self._save(task)

    async def complete(self, user_id: int, task_id: int) -> Task:
        return await self.update(user_id, task_id, {"status": TaskStatus.DONE})

    async def reopen(self, user_id: int, task_id: int) -> Task:
        return await self.update(user_id, task_id, {"status": TaskStatus.TODO})

    async def delete(self, user_id: int, task_id: int) -> None:
        await self._tasks.delete(await self.get(user_id, task_id))

    async def _save(self, task: Task, created: bool = False) -> Task:
        return await (self._tasks.add(task) if created else self._tasks.update(task))
