from copy import deepcopy
from datetime import UTC, date, datetime

from aceso.planner.domain.entities import Habit, HabitLog, Task, TaskStatus


class FakeHabitRepository:
    def __init__(self) -> None:
        self.habits: dict[int, Habit] = {}
        self.logs: dict[tuple[int, date], HabitLog] = {}
        self._id = 0
        self._log_id = 0

    async def add(self, habit: Habit) -> Habit:
        habit = deepcopy(habit)
        self._id += 1
        habit.id = self._id
        habit.created_at = habit.updated_at = datetime.now(UTC)
        self.habits[habit.id] = habit
        return deepcopy(habit)

    async def get(self, user_id: int, habit_id: int) -> Habit | None:
        habit = self.habits.get(habit_id)
        return deepcopy(habit) if habit and habit.user_id == user_id else None

    async def list_all(self, user_id: int, include_archived: bool) -> list[Habit]:
        return [
            deepcopy(h)
            for h in self.habits.values()
            if h.user_id == user_id and (include_archived or h.archived_at is None)
        ]

    async def update(self, habit: Habit) -> Habit:
        assert habit.id is not None
        habit = deepcopy(habit)
        habit.updated_at = datetime.now(UTC)
        self.habits[habit.id] = habit
        return deepcopy(habit)

    async def delete(self, habit: Habit) -> None:
        assert habit.id is not None
        self.habits.pop(habit.id, None)
        self.logs = {k: v for k, v in self.logs.items() if k[0] != habit.id}

    async def upsert_log(self, log: HabitLog) -> HabitLog:
        log = deepcopy(log)
        existing = self.logs.get((log.habit_id, log.day))
        if existing is None:
            self._log_id += 1
            log.id = self._log_id
        else:
            log.id = existing.id
        self.logs[(log.habit_id, log.day)] = log
        return deepcopy(log)

    async def delete_log(self, habit_id: int, day: date) -> bool:
        return self.logs.pop((habit_id, day), None) is not None

    async def list_logs(
        self, habit_id: int, start: date | None = None, end: date | None = None
    ) -> list[HabitLog]:
        return sorted(
            (
                deepcopy(log)
                for (hid, day), log in self.logs.items()
                if hid == habit_id
                and (start is None or day >= start)
                and (end is None or day <= end)
            ),
            key=lambda log: log.day,
        )

    async def list_user_logs(self, user_id: int, start: date, end: date) -> list[HabitLog]:
        owned = {h.id for h in self.habits.values() if h.user_id == user_id}
        return sorted(
            (
                deepcopy(log)
                for (hid, day), log in self.logs.items()
                if hid in owned and start <= day <= end
            ),
            key=lambda log: (log.day, log.habit_id),
        )


class FakeTaskRepository:
    def __init__(self) -> None:
        self.tasks: dict[int, Task] = {}
        self._id = 0

    async def add(self, task: Task) -> Task:
        task = deepcopy(task)
        self._id += 1
        task.id = self._id
        task.created_at = task.updated_at = datetime.now(UTC)
        self.tasks[task.id] = task
        return deepcopy(task)

    async def get(self, user_id: int, task_id: int) -> Task | None:
        task = self.tasks.get(task_id)
        return deepcopy(task) if task and task.user_id == user_id else None

    async def list_filtered(
        self,
        user_id: int,
        status: TaskStatus | None = None,
        due_from: date | None = None,
        due_to: date | None = None,
    ) -> list[Task]:
        return [
            deepcopy(t)
            for t in self.tasks.values()
            if t.user_id == user_id
            and (status is None or t.status == status)
            and (due_from is None or (t.due_date is not None and t.due_date >= due_from))
            and (due_to is None or (t.due_date is not None and t.due_date <= due_to))
        ]

    async def update(self, task: Task) -> Task:
        assert task.id is not None
        task = deepcopy(task)
        task.updated_at = datetime.now(UTC)
        self.tasks[task.id] = task
        return deepcopy(task)

    async def delete(self, task: Task) -> None:
        assert task.id is not None
        self.tasks.pop(task.id, None)
