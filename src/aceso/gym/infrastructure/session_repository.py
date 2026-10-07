from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aceso.gym.domain.entities import (
    ExerciseSet,
    SessionExercise,
    SessionStatus,
    SetInterval,
    WorkoutSession,
)
from aceso.gym.infrastructure.models import (
    ExerciseSetModel,
    SessionExerciseModel,
    SetIntervalModel,
    WorkoutSessionModel,
)

_INTERVAL_FIELDS = ("position", "duration_s", "distance_m", "speed", "incline_pct", "level")
_SET_FIELDS = (
    "set_number",
    "reps",
    "weight_kg",
    "added_weight_kg",
    "duration_s",
    "distance_m",
    "rpe",
    "completed",
    "notes",
)


def _interval_entity(model: SetIntervalModel) -> SetInterval:
    return SetInterval(**{f: getattr(model, f) for f in _INTERVAL_FIELDS})


def _set_entity(model: ExerciseSetModel) -> ExerciseSet:
    return ExerciseSet(
        id=model.id,
        session_exercise_id=model.session_exercise_id,
        intervals=[_interval_entity(i) for i in model.intervals],
        **{f: getattr(model, f) for f in _SET_FIELDS},
    )


def _exercise_entity(model: SessionExerciseModel) -> SessionExercise:
    return SessionExercise(
        id=model.id,
        session_id=model.session_id,
        exercise_id=model.exercise_id,
        position=model.position,
        notes=model.notes,
        sets=[_set_entity(s) for s in model.sets],
    )


def _session_entity(model: WorkoutSessionModel) -> WorkoutSession:
    return WorkoutSession(
        id=model.id,
        user_id=model.user_id,
        scheduled_date=model.scheduled_date,
        status=SessionStatus(model.status),
        routine_id=model.routine_id,
        started_at=model.started_at,
        finished_at=model.finished_at,
        notes=model.notes,
        created_at=model.created_at,
        exercises=[_exercise_entity(e) for e in model.items],
    )


def _interval_models(intervals: list[SetInterval]) -> list[SetIntervalModel]:
    return [SetIntervalModel(**{f: getattr(i, f) for f in _INTERVAL_FIELDS}) for i in intervals]


def _set_model(exercise_set: ExerciseSet) -> ExerciseSetModel:
    return ExerciseSetModel(
        intervals=_interval_models(exercise_set.intervals),
        **{f: getattr(exercise_set, f) for f in _SET_FIELDS},
    )


def _exercise_model(item: SessionExercise) -> SessionExerciseModel:
    return SessionExerciseModel(
        exercise_id=item.exercise_id,
        position=item.position,
        notes=item.notes,
        sets=[_set_model(s) for s in item.sets],
    )


class SqlAlchemyWorkoutSessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, session: WorkoutSession) -> WorkoutSession:
        model = WorkoutSessionModel(
            user_id=session.user_id,
            scheduled_date=session.scheduled_date,
            status=SessionStatus(session.status).value,
            routine_id=session.routine_id,
            started_at=session.started_at,
            finished_at=session.finished_at,
            notes=session.notes,
            items=[_exercise_model(e) for e in session.exercises],
        )
        self._session.add(model)
        await self._session.flush()
        loaded = await self._load_session(session.user_id, model.id)
        assert loaded is not None
        return _session_entity(loaded)

    async def get(self, user_id: int, session_id: int) -> WorkoutSession | None:
        model = await self._load_session(user_id, session_id)
        return _session_entity(model) if model else None

    async def list_range(self, user_id: int, start: date, end: date) -> list[WorkoutSession]:
        stmt = (
            select(WorkoutSessionModel)
            .where(
                WorkoutSessionModel.user_id == user_id,
                WorkoutSessionModel.scheduled_date.between(start, end),
            )
            .order_by(WorkoutSessionModel.scheduled_date, WorkoutSessionModel.id)
        )
        return [_session_entity(m) for m in await self._session.scalars(stmt)]

    async def update(self, session: WorkoutSession) -> WorkoutSession:
        assert session.id is not None
        model = await self._load_session(session.user_id, session.id)
        assert model is not None
        model.scheduled_date = session.scheduled_date
        model.status = SessionStatus(session.status).value
        model.started_at = session.started_at
        model.finished_at = session.finished_at
        model.notes = session.notes
        await self._session.flush()
        return _session_entity(model)

    async def delete(self, session: WorkoutSession) -> None:
        assert session.id is not None
        model = await self._load_session(session.user_id, session.id, populate=False)
        if model is not None:
            await self._session.delete(model)
            await self._session.flush()

    async def add_exercise(self, session_id: int, item: SessionExercise) -> SessionExercise:
        model = _exercise_model(item)
        model.session_id = session_id
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model, ["sets"])
        return _exercise_entity(model)

    async def get_exercise(self, user_id: int, session_exercise_id: int) -> SessionExercise | None:
        model = await self._load_exercise(user_id, session_exercise_id)
        return _exercise_entity(model) if model else None

    async def delete_exercise(self, user_id: int, session_exercise_id: int) -> None:
        model = await self._load_exercise(user_id, session_exercise_id)
        if model is not None:
            await self._session.delete(model)
            await self._session.flush()

    async def add_set(self, session_exercise_id: int, exercise_set: ExerciseSet) -> ExerciseSet:
        model = _set_model(exercise_set)
        model.session_exercise_id = session_exercise_id
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model, ["intervals"])
        return _set_entity(model)

    async def get_set(self, user_id: int, set_id: int) -> ExerciseSet | None:
        model = await self._load_set(user_id, set_id)
        return _set_entity(model) if model else None

    async def update_set(self, user_id: int, exercise_set: ExerciseSet) -> ExerciseSet:
        assert exercise_set.id is not None
        model = await self._load_set(user_id, exercise_set.id)
        assert model is not None
        for name in _SET_FIELDS:
            setattr(model, name, getattr(exercise_set, name))
        # Delete old intervals first so (set_id, position) stays unique.
        model.intervals.clear()
        await self._session.flush()
        model.intervals.extend(_interval_models(exercise_set.intervals))
        await self._session.flush()
        await self._session.refresh(model, ["intervals"])
        return _set_entity(model)

    async def delete_set(self, user_id: int, set_id: int) -> None:
        model = await self._load_set(user_id, set_id)
        if model is not None:
            await self._session.delete(model)
            await self._session.flush()

    async def _load_session(
        self, user_id: int, session_id: int, *, populate: bool = True
    ) -> WorkoutSessionModel | None:
        stmt = select(WorkoutSessionModel).where(
            WorkoutSessionModel.id == session_id, WorkoutSessionModel.user_id == user_id
        )
        if populate:
            stmt = stmt.execution_options(populate_existing=True)
        return await self._session.scalar(stmt)

    async def _load_exercise(
        self, user_id: int, session_exercise_id: int
    ) -> SessionExerciseModel | None:
        stmt = (
            select(SessionExerciseModel)
            .join(WorkoutSessionModel, WorkoutSessionModel.id == SessionExerciseModel.session_id)
            .where(
                SessionExerciseModel.id == session_exercise_id,
                WorkoutSessionModel.user_id == user_id,
            )
            .execution_options(populate_existing=True)
        )
        return await self._session.scalar(stmt)

    async def _load_set(self, user_id: int, set_id: int) -> ExerciseSetModel | None:
        stmt = (
            select(ExerciseSetModel)
            .join(
                SessionExerciseModel,
                SessionExerciseModel.id == ExerciseSetModel.session_exercise_id,
            )
            .join(WorkoutSessionModel, WorkoutSessionModel.id == SessionExerciseModel.session_id)
            .where(ExerciseSetModel.id == set_id, WorkoutSessionModel.user_id == user_id)
            .execution_options(populate_existing=True)
        )
        return await self._session.scalar(stmt)
