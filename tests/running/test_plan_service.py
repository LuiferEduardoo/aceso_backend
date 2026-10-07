from datetime import date

import pytest

from aceso.running.application.plans import TrainingPlanService
from aceso.running.domain.entities import PlannedRun, RunType, TrainingPlan
from aceso.shared.domain.errors import InvalidOperationError, NotFoundError
from tests.running.fakes import FakeTrainingPlanRepository


@pytest.fixture
def service() -> TrainingPlanService:
    return TrainingPlanService(FakeTrainingPlanRepository())


def _plan(**kwargs: object) -> TrainingPlan:
    values: dict = {
        "user_id": 1,
        "name": "10K",
        "start_date": date(2026, 10, 1),
        "end_date": date(2026, 11, 30),
    }
    values.update(kwargs)
    return TrainingPlan(**values)


async def test_plan_dates_are_validated(service: TrainingPlanService) -> None:
    with pytest.raises(InvalidOperationError):
        await service.create(_plan(end_date=date(2026, 9, 1)))
    with pytest.raises(InvalidOperationError):
        await service.create(_plan(runs=[PlannedRun(scheduled_date=date(2026, 12, 25))]))


async def test_runs_must_stay_inside_plan(service: TrainingPlanService) -> None:
    plan = await service.create(_plan())
    assert plan.id
    run = await service.add_run(
        1, plan.id, PlannedRun(scheduled_date=date(2026, 10, 4), run_type=RunType.LONG)
    )
    assert run.id and run.plan_id == plan.id
    with pytest.raises(InvalidOperationError):
        await service.update_run(1, run.id, {"scheduled_date": date(2027, 1, 1)})
    with pytest.raises(InvalidOperationError):
        await service.update(1, plan.id, {"end_date": date(2026, 10, 2)})


async def test_runs_between_is_scoped_to_user(service: TrainingPlanService) -> None:
    mine = await service.create(_plan(runs=[PlannedRun(scheduled_date=date(2026, 10, 5))]))
    await service.create(_plan(user_id=2, runs=[PlannedRun(scheduled_date=date(2026, 10, 5))]))
    runs = await service.runs_between(1, date(2026, 10, 1), date(2026, 10, 31))
    assert [r.plan_id for r in runs] == [mine.id]
    with pytest.raises(NotFoundError):
        await service.get_run(2, runs[0].id or 0)
