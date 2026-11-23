from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from aceso.planner.application.habit_stats import StreakUnit, compute_stats
from aceso.planner.domain.entities import Habit, HabitFrequency, HabitLog

START = date(2026, 10, 5)  # a Monday
BOGOTA = ZoneInfo("America/Bogota")


def _habit(**kwargs: object) -> Habit:
    values: dict = {"user_id": 1, "name": "Read", "start_date": START, "id": 1}
    values.update(kwargs)
    return Habit(**values)


def _logs(*days: date, count: int = 1) -> list[HabitLog]:
    return [HabitLog(habit_id=1, day=d, count=count) for d in days]


def _day(offset: int) -> date:
    return START + timedelta(days=offset)


def test_daily_streaks_and_rate() -> None:
    habit = _habit()
    # Done days 0,1,2 then a gap on 3, then 4,5 (today = 6, not logged yet).
    logs = _logs(_day(0), _day(1), _day(2), _day(4), _day(5))

    stats = compute_stats(habit, logs, START, _day(6), today=_day(6))

    assert stats.streak_unit == StreakUnit.DAY
    assert stats.current_streak == 2  # today is still in progress, does not break it
    assert stats.best_streak == 3
    assert (stats.completed, stats.expected) == (5, 7)
    assert stats.completion_rate == round(5 / 7, 4)


def test_daily_streak_broken_by_yesterday() -> None:
    stats = compute_stats(_habit(), _logs(_day(0), _day(1)), START, _day(3), today=_day(3))
    assert stats.current_streak == 0
    assert stats.best_streak == 2


def test_target_count_must_be_reached() -> None:
    habit = _habit(target_count=3)
    logs = [*_logs(_day(0), count=3), *_logs(_day(1), count=2)]
    stats = compute_stats(habit, logs, START, _day(1), today=_day(1))
    assert stats.completed == 1
    assert stats.current_streak == 1


def test_weekdays_skip_unscheduled_days() -> None:
    habit = _habit(frequency=HabitFrequency.WEEKDAYS, weekdays=[0, 2, 4])  # Mon, Wed, Fri
    logs = _logs(_day(0), _day(2), _day(4), _day(7))  # Mon, Wed, Fri, next Mon

    stats = compute_stats(habit, logs, START, _day(8), today=_day(8))  # today = Tuesday

    assert stats.current_streak == 4
    assert stats.best_streak == 4
    assert (stats.completed, stats.expected) == (4, 4)
    assert stats.completion_rate == 1.0


def test_times_per_week_counts_weeks() -> None:
    habit = _habit(frequency=HabitFrequency.TIMES_PER_WEEK, times_per_week=2)
    logs = _logs(
        _day(0),
        _day(3),  # week 1: met
        _day(8),
        _day(9),  # week 2: met
        _day(15),  # week 3: only once
        _day(21),
        _day(22),  # week 4: met
        _day(29),  # week 5 (current, in progress): once
    )

    stats = compute_stats(habit, logs, START, _day(30), today=_day(30))

    assert stats.streak_unit == StreakUnit.WEEK
    assert stats.current_streak == 1
    assert stats.best_streak == 2
    assert stats.expected == 10
    assert stats.completed == 2 + 2 + 1 + 2 + 1


def test_rate_ignores_days_before_start_and_after_today_or_archive() -> None:
    archived_at = datetime.combine(_day(2), datetime.min.time(), tzinfo=BOGOTA)
    habit = _habit(archived_at=archived_at)
    stats = compute_stats(
        habit, _logs(_day(0), _day(1)), date(2026, 9, 1), _day(30), today=_day(10)
    )
    assert (stats.completed, stats.expected) == (2, 3)

    # 00:00Z on day 2 is still day 1 in Bogota, so the habit was archived on day 1.
    habit.archived_at = archived_at.astimezone(UTC).replace(hour=0)
    stats = compute_stats(
        habit, _logs(_day(0), _day(1)), date(2026, 9, 1), _day(30), today=_day(10)
    )
    assert (stats.completed, stats.expected) == (2, 2)


def test_no_expected_days_gives_zero_rate() -> None:
    stats = compute_stats(_habit(), [], date(2026, 9, 1), date(2026, 9, 30), today=_day(5))
    assert stats.expected == 0 and stats.completion_rate == 0.0
