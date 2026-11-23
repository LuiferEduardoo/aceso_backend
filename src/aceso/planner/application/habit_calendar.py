"""How a habit appears in Google Calendar: one recurring event built from its frequency."""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from aceso.planner.domain.entities import Habit, HabitFrequency

DEFAULT_DURATION = timedelta(minutes=30)
_BYDAY = ("MO", "TU", "WE", "TH", "FR", "SA", "SU")


def habit_rrule(habit: Habit) -> str:
    """RFC 5545 rule. times_per_week has no fixed days, so it is offered as a daily slot."""
    if habit.frequency == HabitFrequency.WEEKDAYS:
        days = ",".join(_BYDAY[d] for d in sorted(habit.weekdays))
        return f"RRULE:FREQ=WEEKLY;BYDAY={days}"
    return "RRULE:FREQ=DAILY"


def habit_wants_event(habit: Habit) -> bool:
    return habit.sync_to_calendar and habit.time_of_day is not None and not habit.archived


def _first_day(habit: Habit) -> date:
    day = habit.start_date
    for _ in range(7):
        if habit.scheduled_on(day):
            return day
        day += timedelta(days=1)
    return habit.start_date


def habit_event_window(habit: Habit) -> tuple[datetime, datetime]:
    """UTC start/end of the first occurrence, using the habit's own timezone."""
    assert habit.time_of_day is not None
    local = datetime.combine(_first_day(habit), habit.time_of_day, tzinfo=ZoneInfo(habit.timezone))
    start = local.astimezone(UTC)
    duration = timedelta(minutes=habit.duration_min) if habit.duration_min else DEFAULT_DURATION
    return start, start + duration
