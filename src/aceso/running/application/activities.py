from datetime import UTC, date, datetime, time, timedelta

from aceso.running.domain.entities import Activity
from aceso.running.domain.ports import ActivityRepository
from aceso.shared.domain.errors import InvalidOperationError, NotFoundError

MAX_RANGE_DAYS = 366


class ActivityQueries:
    def __init__(self, activities: ActivityRepository) -> None:
        self._activities = activities

    async def between(self, user_id: int, start: date, end: date) -> list[Activity]:
        """Activities that started from `start` 00:00 UTC through the end of `end` (UTC)."""
        if end < start:
            raise InvalidOperationError("'to' must be on or after 'from'")
        if (end - start).days > MAX_RANGE_DAYS:
            raise InvalidOperationError(f"Range cannot exceed {MAX_RANGE_DAYS} days")
        return await self._activities.list_range(
            user_id,
            datetime.combine(start, time.min, tzinfo=UTC),
            datetime.combine(end + timedelta(days=1), time.min, tzinfo=UTC),
        )

    async def get(self, user_id: int, activity_id: int) -> Activity:
        activity = await self._activities.get(user_id, activity_id)
        if activity is None:
            raise NotFoundError("Activity not found")
        return activity
