from datetime import date
from typing import Protocol

from aceso.planner.domain.entities import Habit, HabitLog, Task, TaskStatus


class HabitRepository(Protocol):
    async def add(self, habit: Habit) -> Habit: ...

    async def get(self, user_id: int, habit_id: int) -> Habit | None: ...

    async def list_all(self, user_id: int, include_archived: bool) -> list[Habit]: ...

    async def update(self, habit: Habit) -> Habit: ...

    async def delete(self, habit: Habit) -> None: ...

    async def upsert_log(self, log: HabitLog) -> HabitLog:
        """Insert or replace the log for (habit_id, day)."""
        ...

    async def delete_log(self, habit_id: int, day: date) -> bool:
        """Return True when a log existed."""
        ...

    async def list_logs(
        self, habit_id: int, start: date | None = None, end: date | None = None
    ) -> list[HabitLog]:
        """Logs ordered by day; `start`/`end` are inclusive bounds."""
        ...

    async def list_user_logs(self, user_id: int, start: date, end: date) -> list[HabitLog]: ...


class TaskRepository(Protocol):
    async def add(self, task: Task) -> Task: ...

    async def get(self, user_id: int, task_id: int) -> Task | None: ...

    async def list_filtered(
        self,
        user_id: int,
        status: TaskStatus | None = None,
        due_from: date | None = None,
        due_to: date | None = None,
    ) -> list[Task]: ...

    async def update(self, task: Task) -> Task: ...

    async def delete(self, task: Task) -> None: ...
