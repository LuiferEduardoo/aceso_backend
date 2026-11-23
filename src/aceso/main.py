from fastapi import FastAPI

from aceso.gym.api.exercises import router as gym_exercises_router
from aceso.gym.api.routines import router as gym_routines_router
from aceso.gym.api.sessions import session_exercises_router, sessions_router, sets_router
from aceso.health.api.router import router as health_router
from aceso.identity.api.router import router as auth_router
from aceso.planner.api.calendar import agenda_router, events_router
from aceso.planner.api.habits import router as planner_habits_router
from aceso.planner.api.tasks import router as planner_tasks_router
from aceso.running.api.plans import planned_runs_router, plans_router
from aceso.running.api.strava import activities_router, strava_router
from aceso.shared.api.errors import register_error_handlers


def create_app() -> FastAPI:
    app = FastAPI(title="Aceso API", version="0.1.0")
    register_error_handlers(app)
    app.include_router(auth_router)
    app.include_router(gym_exercises_router)
    app.include_router(gym_routines_router)
    app.include_router(sessions_router)
    app.include_router(session_exercises_router)
    app.include_router(sets_router)
    app.include_router(health_router)
    app.include_router(plans_router)
    app.include_router(planned_runs_router)
    app.include_router(strava_router)
    app.include_router(activities_router)
    app.include_router(planner_habits_router)
    app.include_router(planner_tasks_router)
    app.include_router(events_router)
    app.include_router(agenda_router)

    @app.get("/healthz", tags=["system"])
    async def health_check() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
