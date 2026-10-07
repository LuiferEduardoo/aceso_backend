from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aceso.running.domain.entities import PlannedRun, RunType, TrainingPlan
from aceso.running.infrastructure.models import PlannedRunModel, TrainingPlanModel

_RUN_FIELDS = (
    "scheduled_date",
    "target_distance_m",
    "target_duration_s",
    "target_pace_s_per_km",
    "description",
)


def _run_entity(model: PlannedRunModel) -> PlannedRun:
    return PlannedRun(
        id=model.id,
        plan_id=model.plan_id,
        run_type=RunType(model.run_type),
        **{f: getattr(model, f) for f in _RUN_FIELDS},
    )


def _apply_run(model: PlannedRunModel, run: PlannedRun) -> PlannedRunModel:
    for name in _RUN_FIELDS:
        setattr(model, name, getattr(run, name))
    model.run_type = RunType(run.run_type).value
    return model


def _plan_entity(model: TrainingPlanModel) -> TrainingPlan:
    return TrainingPlan(
        id=model.id,
        user_id=model.user_id,
        name=model.name,
        goal=model.goal,
        start_date=model.start_date,
        end_date=model.end_date,
        created_at=model.created_at,
        runs=[_run_entity(r) for r in model.runs],
    )


class SqlAlchemyTrainingPlanRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, plan: TrainingPlan) -> TrainingPlan:
        model = TrainingPlanModel(
            user_id=plan.user_id,
            name=plan.name,
            goal=plan.goal,
            start_date=plan.start_date,
            end_date=plan.end_date,
            runs=[_apply_run(PlannedRunModel(), run) for run in plan.runs],
        )
        self._session.add(model)
        await self._session.flush()
        loaded = await self._load(plan.user_id, model.id)
        assert loaded is not None
        return _plan_entity(loaded)

    async def get(self, user_id: int, plan_id: int) -> TrainingPlan | None:
        model = await self._load(user_id, plan_id)
        return _plan_entity(model) if model else None

    async def list_all(self, user_id: int) -> list[TrainingPlan]:
        stmt = (
            select(TrainingPlanModel)
            .where(TrainingPlanModel.user_id == user_id)
            .order_by(TrainingPlanModel.start_date.desc(), TrainingPlanModel.id)
        )
        return [_plan_entity(m) for m in await self._session.scalars(stmt)]

    async def update(self, plan: TrainingPlan) -> TrainingPlan:
        assert plan.id is not None
        model = await self._load(plan.user_id, plan.id)
        assert model is not None
        model.name, model.goal = plan.name, plan.goal
        model.start_date, model.end_date = plan.start_date, plan.end_date
        await self._session.flush()
        return _plan_entity(model)

    async def delete(self, plan: TrainingPlan) -> None:
        assert plan.id is not None
        model = await self._load(plan.user_id, plan.id)
        if model is not None:
            await self._session.delete(model)
            await self._session.flush()

    async def add_run(self, run: PlannedRun) -> PlannedRun:
        model = _apply_run(PlannedRunModel(plan_id=run.plan_id), run)
        self._session.add(model)
        await self._session.flush()
        return _run_entity(model)

    async def get_run(self, user_id: int, run_id: int) -> PlannedRun | None:
        model = await self._load_run(user_id, run_id)
        return _run_entity(model) if model else None

    async def list_runs(self, user_id: int, start: date, end: date) -> list[PlannedRun]:
        stmt = (
            select(PlannedRunModel)
            .join(TrainingPlanModel, TrainingPlanModel.id == PlannedRunModel.plan_id)
            .where(
                TrainingPlanModel.user_id == user_id,
                PlannedRunModel.scheduled_date.between(start, end),
            )
            .order_by(PlannedRunModel.scheduled_date, PlannedRunModel.id)
        )
        return [_run_entity(m) for m in await self._session.scalars(stmt)]

    async def update_run(self, run: PlannedRun) -> PlannedRun:
        assert run.id is not None
        model = await self._session.get(PlannedRunModel, run.id)
        assert model is not None
        _apply_run(model, run)
        await self._session.flush()
        return _run_entity(model)

    async def delete_run(self, run: PlannedRun) -> None:
        model = await self._session.get(PlannedRunModel, run.id)
        if model is not None:
            await self._session.delete(model)
            await self._session.flush()

    async def _load(self, user_id: int, plan_id: int) -> TrainingPlanModel | None:
        stmt = (
            select(TrainingPlanModel)
            .where(TrainingPlanModel.id == plan_id, TrainingPlanModel.user_id == user_id)
            .execution_options(populate_existing=True)
        )
        return await self._session.scalar(stmt)

    async def _load_run(self, user_id: int, run_id: int) -> PlannedRunModel | None:
        stmt = (
            select(PlannedRunModel)
            .join(TrainingPlanModel, TrainingPlanModel.id == PlannedRunModel.plan_id)
            .where(PlannedRunModel.id == run_id, TrainingPlanModel.user_id == user_id)
        )
        return await self._session.scalar(stmt)
