from aceso.health.domain.entities import HealthBatch, HealthSource, IngestResult
from aceso.health.domain.ports import HealthRepository
from aceso.shared.domain.errors import InvalidOperationError


class IngestHealthData:
    """Store a batch from any source. Re-sending the same data updates instead of duplicating."""

    def __init__(self, repository: HealthRepository) -> None:
        self._repository = repository

    async def execute(self, user_id: int, source: HealthSource, batch: HealthBatch) -> IngestResult:
        for sleep in batch.sleep_sessions:
            if sleep.end_at <= sleep.start_at:
                raise InvalidOperationError("Sleep end_at must be after start_at")

        # Last item wins when a batch repeats a key (an upsert cannot touch a row twice).
        summaries = {s.day: s for s in batch.daily_summaries}
        samples = {(s.metric, s.recorded_at): s for s in batch.samples}
        sleeps = {s.start_at: s for s in batch.sleep_sessions}
        for item in (*summaries.values(), *samples.values(), *sleeps.values()):
            item.user_id = user_id
            item.source = source

        if summaries:
            await self._repository.upsert_daily_summaries(list(summaries.values()))
        if samples:
            await self._repository.upsert_samples(list(samples.values()))
        if sleeps:
            await self._repository.upsert_sleep_sessions(list(sleeps.values()))
        return IngestResult(
            daily_summaries=len(summaries), samples=len(samples), sleep_sessions=len(sleeps)
        )
