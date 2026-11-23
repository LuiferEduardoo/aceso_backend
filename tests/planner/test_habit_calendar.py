from datetime import UTC, date, datetime, time

from aceso.planner.application.habit_calendar import (
    habit_event_window,
    habit_rrule,
    habit_wants_event,
)
from aceso.planner.domain.entities import Habit, HabitFrequency


def _habit(**kwargs: object) -> Habit:
    values: dict = {
        "user_id": 1,
        "name": "Run",
        "start_date": date(2026, 10, 7),  # Wednesday
        "time_of_day": time(7, 30),
        "sync_to_calendar": True,
    }
    values.update(kwargs)
    return Habit(**values)


def test_rrule_from_frequency() -> None:
    assert habit_rrule(_habit()) == "RRULE:FREQ=DAILY"
    weekly = _habit(frequency=HabitFrequency.WEEKDAYS, weekdays=[4, 0, 2])
    assert habit_rrule(weekly) == "RRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR"
    flexible = _habit(frequency=HabitFrequency.TIMES_PER_WEEK, times_per_week=3)
    assert habit_rrule(flexible) == "RRULE:FREQ=DAILY"


def test_first_occurrence_uses_habit_timezone_and_weekdays() -> None:
    habit = _habit(
        frequency=HabitFrequency.WEEKDAYS,
        weekdays=[4],  # first Friday on/after the start: 2026-10-09
        timezone="Europe/Madrid",  # UTC+2 in October
        duration_min=45,
    )
    start, end = habit_event_window(habit)
    assert start == datetime(2026, 10, 9, 5, 30, tzinfo=UTC)
    assert (end - start).total_seconds() == 45 * 60

    start, end = habit_event_window(_habit())  # default zone: America/Bogota (UTC-5)
    assert start == datetime(2026, 10, 7, 12, 30, tzinfo=UTC)
    assert (end - start).total_seconds() == 30 * 60


def test_only_active_timed_synced_habits_get_an_event() -> None:
    assert habit_wants_event(_habit())
    assert not habit_wants_event(_habit(sync_to_calendar=False))
    assert not habit_wants_event(_habit(time_of_day=None))
    assert not habit_wants_event(_habit(archived_at=datetime(2026, 10, 8, tzinfo=UTC)))
