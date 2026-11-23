from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query, status

from aceso.identity.api.deps import CurrentUserIdDep
from aceso.planner.api.common import ResourceId, reject_nulls
from aceso.planner.api.deps import AgendaDep, CalendarServiceDep
from aceso.planner.api.schemas import (
    AgendaDayRead,
    AgendaHabitRead,
    CalendarEventCreate,
    CalendarEventRead,
    CalendarEventUpdate,
    TaskRead,
)
from aceso.planner.application.agenda import AgendaDay
from aceso.planner.domain.entities import CalendarEvent

events_router = APIRouter(prefix="/planner/events", tags=["planner"])
agenda_router = APIRouter(prefix="/planner/agenda", tags=["planner"])

FromDate = Annotated[date, Query(alias="from")]
ToDate = Annotated[date, Query(alias="to")]


@events_router.post("", status_code=status.HTTP_201_CREATED)
async def create_event(
    payload: CalendarEventCreate, user_id: CurrentUserIdDep, service: CalendarServiceDep
) -> CalendarEventRead:
    event = await service.create(CalendarEvent(user_id=user_id, **payload.model_dump()))
    return CalendarEventRead.model_validate(event)


@events_router.get("", summary="Events overlapping the UTC days from..to")
async def list_events(
    start: FromDate, end: ToDate, user_id: CurrentUserIdDep, service: CalendarServiceDep
) -> list[CalendarEventRead]:
    events = await service.between(user_id, start, end)
    return [CalendarEventRead.model_validate(e) for e in events]


@events_router.get("/{event_id}")
async def get_event(
    event_id: ResourceId, user_id: CurrentUserIdDep, service: CalendarServiceDep
) -> CalendarEventRead:
    return CalendarEventRead.model_validate(await service.get(user_id, event_id))


@events_router.patch("/{event_id}")
async def update_event(
    event_id: ResourceId,
    payload: CalendarEventUpdate,
    user_id: CurrentUserIdDep,
    service: CalendarServiceDep,
) -> CalendarEventRead:
    changes = payload.model_dump(exclude_unset=True)
    reject_nulls(changes, "title", "start_at", "end_at", "all_day")
    return CalendarEventRead.model_validate(await service.update(user_id, event_id, changes))


@events_router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    event_id: ResourceId, user_id: CurrentUserIdDep, service: CalendarServiceDep
) -> None:
    await service.delete(user_id, event_id)


def _day_read(day: AgendaDay) -> AgendaDayRead:
    return AgendaDayRead(
        date=day.day,
        events=[CalendarEventRead.model_validate(e) for e in day.events],
        tasks=[TaskRead.model_validate(t) for t in day.tasks],
        habits=[
            AgendaHabitRead(
                habit_id=o.habit.id or 0,
                name=o.habit.name,
                time_of_day=o.habit.time_of_day,
                duration_min=o.habit.duration_min,
                target_count=o.habit.target_count,
                count=o.count,
                completed=o.completed,
            )
            for o in day.habits
        ],
    )


@agenda_router.get("", summary="Per-day events, due/scheduled tasks and habits (UTC days)")
async def agenda(
    start: FromDate, end: ToDate, user_id: CurrentUserIdDep, agenda: AgendaDep
) -> list[AgendaDayRead]:
    return [_day_read(day) for day in await agenda.between(user_id, start, end)]
