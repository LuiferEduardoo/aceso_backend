from typing import Annotated

from fastapi import Depends

from aceso.identity.api.deps import JwtServiceDep
from aceso.running.application.plans import TrainingPlanService
from aceso.running.domain.ports import ActivityRepository, OAuthStateSigner, StravaGateway
from aceso.running.infrastructure.activity_repository import SqlAlchemyActivityRepository
from aceso.running.infrastructure.plan_repository import SqlAlchemyTrainingPlanRepository
from aceso.running.infrastructure.strava import StravaClient
from aceso.shared.api.deps import SessionDep, SettingsDep
from aceso.shared.infrastructure.oauth_state import JwtOAuthStateSigner

STRAVA_STATE_PURPOSE = "strava_oauth_state"


def get_training_plan_service(session: SessionDep) -> TrainingPlanService:
    return TrainingPlanService(
        SqlAlchemyTrainingPlanRepository(session), SqlAlchemyActivityRepository(session)
    )


TrainingPlanServiceDep = Annotated[TrainingPlanService, Depends(get_training_plan_service)]


def get_strava_gateway(settings: SettingsDep) -> StravaGateway:
    return StravaClient(
        settings.strava_client_id, settings.strava_client_secret, settings.strava_redirect_uri
    )


StravaGatewayDep = Annotated[StravaGateway, Depends(get_strava_gateway)]


def get_oauth_state_signer(jwt_service: JwtServiceDep) -> OAuthStateSigner:
    return JwtOAuthStateSigner(jwt_service, STRAVA_STATE_PURPOSE)


OAuthStateSignerDep = Annotated[OAuthStateSigner, Depends(get_oauth_state_signer)]


def get_activity_repository(session: SessionDep) -> ActivityRepository:
    return SqlAlchemyActivityRepository(session)


ActivityRepositoryDep = Annotated[ActivityRepository, Depends(get_activity_repository)]
