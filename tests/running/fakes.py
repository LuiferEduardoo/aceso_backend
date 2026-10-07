from copy import deepcopy
from datetime import UTC, date, datetime

from aceso.running.domain.entities import PlannedRun, TrainingPlan


class FakeTrainingPlanRepository:
    def __init__(self) -> None:
        self.plans: dict[int, TrainingPlan] = {}
        self._plan_id = 0
        self._run_id = 0

    def _new_run_id(self) -> int:
        self._run_id += 1
        return self._run_id

    async def add(self, plan: TrainingPlan) -> TrainingPlan:
        plan = deepcopy(plan)
        self._plan_id += 1
        plan.id, plan.created_at = self._plan_id, datetime.now(UTC)
        for run in plan.runs:
            run.id, run.plan_id = self._new_run_id(), plan.id
        self.plans[plan.id] = plan
        return deepcopy(plan)

    async def get(self, user_id: int, plan_id: int) -> TrainingPlan | None:
        plan = self.plans.get(plan_id)
        return deepcopy(plan) if plan and plan.user_id == user_id else None

    async def list_all(self, user_id: int) -> list[TrainingPlan]:
        return [deepcopy(p) for p in self.plans.values() if p.user_id == user_id]

    async def update(self, plan: TrainingPlan) -> TrainingPlan:
        assert plan.id is not None
        plan = deepcopy(plan)
        plan.runs = self.plans[plan.id].runs
        self.plans[plan.id] = plan
        return deepcopy(plan)

    async def delete(self, plan: TrainingPlan) -> None:
        assert plan.id is not None
        self.plans.pop(plan.id, None)

    async def add_run(self, run: PlannedRun) -> PlannedRun:
        assert run.plan_id is not None
        run = deepcopy(run)
        run.id = self._new_run_id()
        self.plans[run.plan_id].runs.append(run)
        return deepcopy(run)

    def _find(self, user_id: int, run_id: int) -> tuple[TrainingPlan, int] | None:
        for plan in self.plans.values():
            for index, run in enumerate(plan.runs):
                if run.id == run_id and plan.user_id == user_id:
                    return plan, index
        return None

    async def get_run(self, user_id: int, run_id: int) -> PlannedRun | None:
        found = self._find(user_id, run_id)
        return deepcopy(found[0].runs[found[1]]) if found else None

    async def list_runs(self, user_id: int, start: date, end: date) -> list[PlannedRun]:
        return [
            deepcopy(r)
            for p in self.plans.values()
            if p.user_id == user_id
            for r in p.runs
            if start <= r.scheduled_date <= end
        ]

    async def update_run(self, run: PlannedRun) -> PlannedRun:
        for plan in self.plans.values():
            for index, existing in enumerate(plan.runs):
                if existing.id == run.id:
                    plan.runs[index] = deepcopy(run)
        return deepcopy(run)

    async def delete_run(self, run: PlannedRun) -> None:
        for plan in self.plans.values():
            plan.runs = [r for r in plan.runs if r.id != run.id]
