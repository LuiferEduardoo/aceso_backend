"""Pure streak / completion-rate math for habits (no I/O, easy to unit test)."""

from collections import Counter
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo

from aceso.planner.application.ranges import DEFAULT_TZ, local_day
from aceso.planner.domain.entities import Habit, HabitFrequency, HabitLog


class StreakUnit(StrEnum):
    DAY = "day"
    WEEK = "week"


@dataclass(frozen=True, slots=True)
class HabitStats:
    streak_unit: StreakUnit
    current_streak: int
    best_streak: int
    completed: int
    expected: int
    completion_rate: float


def _days(start: date, end: date) -> Iterator[date]:
    day = start
    while day <= end:
        yield day
        day += timedelta(days=1)


def week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _best_run(flags: Iterable[bool]) -> int:
    best = run = 0
    for ok in flags:
        run = run + 1 if ok else 0
        best = max(best, run)
    return best


def _current_run(flags_newest_first: list[bool]) -> int:
    """Consecutive successes from the newest period; the newest may still be in progress."""
    flags = flags_newest_first
    if flags and not flags[0]:
        flags = flags[1:]
    run = 0
    for ok in flags:
        if not ok:
            break
        run += 1
    return run


def _rate(completed: int, expected: int) -> float:
    return round(completed / expected, 4) if expected else 0.0


def compute_stats(
    habit: Habit,
    logs: Iterable[HabitLog],
    start: date,
    end: date,
    today: date,
    tz: ZoneInfo = DEFAULT_TZ,
) -> HabitStats:
    """Streaks are measured up to `today`; the completion rate covers [start, end] ∩ past."""
    last = today
    if habit.archived_at is not None:
        last = min(last, local_day(habit.archived_at, tz))
    done = {log.day for log in logs if log.meets(habit) and log.day >= habit.start_date}
    range_start, range_end = max(start, habit.start_date), min(end, last)

    if habit.frequency == HabitFrequency.TIMES_PER_WEEK:
        return _weekly_stats(habit, done, range_start, range_end, last)

    scheduled = [d for d in _days(habit.start_date, last) if habit.scheduled_on(d)]
    flags = [d in done for d in scheduled]
    in_range = [d for d in scheduled if range_start <= d <= range_end]
    completed = sum(1 for d in in_range if d in done)
    return HabitStats(
        streak_unit=StreakUnit.DAY,
        current_streak=_current_run(flags[::-1]),
        best_streak=_best_run(flags),
        completed=completed,
        expected=len(in_range),
        completion_rate=_rate(completed, len(in_range)),
    )


def _weekly_stats(
    habit: Habit, done: set[date], range_start: date, range_end: date, last: date
) -> HabitStats:
    target = habit.times_per_week or 1
    per_week = Counter(week_start(d) for d in done if d <= last)
    weeks: list[date] = []
    week = week_start(habit.start_date)
    while week <= last:
        weeks.append(week)
        week += timedelta(days=7)
    flags = [per_week[w] >= target for w in weeks]

    in_range = [
        w
        for w in weeks
        if range_start <= range_end and w <= range_end and w + timedelta(6) >= range_start
    ]
    completed = sum(min(per_week[w], target) for w in in_range)
    expected = len(in_range) * target
    return HabitStats(
        streak_unit=StreakUnit.WEEK,
        current_streak=_current_run(flags[::-1]),
        best_streak=_best_run(flags),
        completed=completed,
        expected=expected,
        completion_rate=_rate(completed, expected),
    )
