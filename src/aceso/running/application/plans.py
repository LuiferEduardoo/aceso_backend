from datetime import date
from typing import Any

from aceso.running.domain.entities import PlannedRun, TrainingPlan
from aceso.running.domain.ports import ActivityRepository, TrainingPlanRepository
from aceso.shared.domain.errors import InvalidOperationError, NotFoundError

PLAN_FIELDS = {"name", "goal", "start_date", "end_date"}
RUN_FIELDS = {
    "scheduled_date",
    "run_type",
    "target_distance_m",
    "target_duration_s",
    "target_pace_s_per_km",
    "description",
    "completed_activity_id",
}
MAX_RANGE_DAYS = 366


def _validate_plan(plan: TrainingPlan) -> None:
    if plan.end_date < plan.start_date:
        raise InvalidOperationError("end_date must be on or after start_date")
    for run in plan.runs:
        _validate_run_date(plan, run)


def _validate_run_date(plan: TrainingPlan, run: PlannedRun) -> None:
    if not plan.covers(run.scheduled_date):
        raise InvalidOperationError("Planned run date must fall within the plan dates")


class TrainingPlanService:
    def __init__(
        self, plans: TrainingPlanRepository, activities: ActivityRepository | None = None
    ) -> None:
        self._plans = plans
        self._activities = activities

    async def create(self, plan: TrainingPlan) -> TrainingPlan:
        _validate_plan(plan)
        return await self._plans.add(plan)

    async def list_all(self, user_id: int) -> list[TrainingPlan]:
        return await self._plans.list_all(user_id)

    async def get(self, user_id: int, plan_id: int) -> TrainingPlan:
        plan = await self._plans.get(user_id, plan_id)
        if plan is None:
            raise NotFoundError("Training plan not found")
        return plan

    async def update(self, user_id: int, plan_id: int, changes: dict[str, Any]) -> TrainingPlan:
        plan = await self.get(user_id, plan_id)
        for name, value in changes.items():
            if name in PLAN_FIELDS:
                setattr(plan, name, value)
        _validate_plan(plan)
        await self._plans.update(plan)
        return await self.get(user_id, plan_id)

    async def delete(self, user_id: int, plan_id: int) -> None:
        await self._plans.delete(await self.get(user_id, plan_id))

    async def add_run(self, user_id: int, plan_id: int, run: PlannedRun) -> PlannedRun:
        plan = await self.get(user_id, plan_id)
        _validate_run_date(plan, run)
        run.plan_id = plan.id
        return await self._plans.add_run(run)

    async def runs_between(self, user_id: int, start: date, end: date) -> list[PlannedRun]:
        if end < start:
            raise InvalidOperationError("'to' must be on or after 'from'")
        if (end - start).days > MAX_RANGE_DAYS:
            raise InvalidOperationError(f"Range cannot exceed {MAX_RANGE_DAYS} days")
        return await self._plans.list_runs(user_id, start, end)

    async def get_run(self, user_id: int, run_id: int) -> PlannedRun:
        run = await self._plans.get_run(user_id, run_id)
        if run is None:
            raise NotFoundError("Planned run not found")
        return run

    async def update_run(self, user_id: int, run_id: int, changes: dict[str, Any]) -> PlannedRun:
        run = await self.get_run(user_id, run_id)
        activity_id = changes.get("completed_activity_id")
        if activity_id is not None:
            await self._ensure_activity_owned(user_id, activity_id)
        for name, value in changes.items():
            if name in RUN_FIELDS:
                setattr(run, name, value)
        assert run.plan_id is not None
        _validate_run_date(await self.get(user_id, run.plan_id), run)
        return await self._plans.update_run(run)

    async def delete_run(self, user_id: int, run_id: int) -> None:
        await self._plans.delete_run(await self.get_run(user_id, run_id))

    async def _ensure_activity_owned(self, user_id: int, activity_id: int) -> None:
        if self._activities is None:
            raise RuntimeError("TrainingPlanService needs an ActivityRepository to link activities")
        if await self._activities.get(user_id, activity_id) is None:
            raise NotFoundError("Activity not found")
