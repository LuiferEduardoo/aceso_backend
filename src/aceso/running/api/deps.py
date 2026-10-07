from typing import Annotated

from fastapi import Depends

from aceso.running.application.plans import TrainingPlanService
from aceso.running.infrastructure.plan_repository import SqlAlchemyTrainingPlanRepository
from aceso.shared.api.deps import SessionDep


def get_training_plan_service(session: SessionDep) -> TrainingPlanService:
    return TrainingPlanService(SqlAlchemyTrainingPlanRepository(session))


TrainingPlanServiceDep = Annotated[TrainingPlanService, Depends(get_training_plan_service)]
