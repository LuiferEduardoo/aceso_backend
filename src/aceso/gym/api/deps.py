from typing import Annotated

from fastapi import Depends

from aceso.gym.application.apply_routine import ApplyRoutine
from aceso.gym.application.exercises import ExerciseService
from aceso.gym.application.routines import RoutineService
from aceso.gym.application.sessions import WorkoutSessionService
from aceso.gym.infrastructure.exercise_repository import SqlAlchemyExerciseRepository
from aceso.gym.infrastructure.routine_repository import SqlAlchemyRoutineRepository
from aceso.gym.infrastructure.session_repository import SqlAlchemyWorkoutSessionRepository
from aceso.shared.api.deps import FileStorageDep, SessionDep


def get_exercise_service(session: SessionDep, storage: FileStorageDep) -> ExerciseService:
    return ExerciseService(SqlAlchemyExerciseRepository(session), storage)


ExerciseServiceDep = Annotated[ExerciseService, Depends(get_exercise_service)]


def get_routine_service(session: SessionDep) -> RoutineService:
    return RoutineService(
        SqlAlchemyRoutineRepository(session), SqlAlchemyExerciseRepository(session)
    )


RoutineServiceDep = Annotated[RoutineService, Depends(get_routine_service)]


def get_workout_session_service(session: SessionDep) -> WorkoutSessionService:
    return WorkoutSessionService(
        SqlAlchemyWorkoutSessionRepository(session), SqlAlchemyExerciseRepository(session)
    )


WorkoutSessionServiceDep = Annotated[WorkoutSessionService, Depends(get_workout_session_service)]


def get_apply_routine(session: SessionDep) -> ApplyRoutine:
    return ApplyRoutine(
        SqlAlchemyRoutineRepository(session), SqlAlchemyWorkoutSessionRepository(session)
    )


ApplyRoutineDep = Annotated[ApplyRoutine, Depends(get_apply_routine)]
