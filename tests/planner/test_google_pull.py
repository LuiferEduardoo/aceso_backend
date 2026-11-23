from datetime import UTC, datetime, timedelta

import pytest

from aceso.planner.domain.entities import CalendarEvent, EventSource, Task
from aceso.shared.domain.errors import NotFoundError
from tests.planner.google_mock import FakeGoogleCalendarApi, timed
from tests.planner.sync_harness import NOW, Harness


@pytest.fixture
async def h() -> Harness:
    harness = Harness()
    await harness.connect()
    return harness


async def test_sync_requires_connection() -> None:
    with pytest.raises(NotFoundError):
        await Harness().sync()


async def test_full_then_incremental_pull(h: Harness) -> None:
    h.api.add_remote("a", **timed("2026-10-12T09:00:00+02:00", "2026-10-12T10:00:00+02:00"))
    h.api.add_remote("b", start={"date": "2026-10-13"}, end={"date": "2026-10-14"})
    h.api.add_remote(
        "habit-series",
        extendedProperties={"private": {"aceso_ref": "habit:9"}},
        **timed("2026-10-12T07:00:00Z", "2026-10-12T07:30:00Z"),
    )

    assert await h.sync() == 2
    a, b = h.by_google_id("a"), h.by_google_id("b")
    assert a.source == EventSource.GOOGLE and not a.sync_pending
    assert a.start_at == datetime(2026, 10, 12, 7, tzinfo=UTC)
    assert b.all_day and b.end_at - b.start_at == timedelta(days=1)
    first = h.sync_requests()[0]
    assert "timeMin" in first and "syncToken" not in first
    link = h.links.links[1]
    assert link.sync_token and link.last_synced_at == NOW

    assert await h.sync() == 0  # nothing changed
    assert h.sync_requests()[-1]["syncToken"] == link.sync_token

    h.api.edit_remote("a", summary="Moved")
    h.api.cancel_remote("b")
    assert await h.sync() == 2
    assert h.by_google_id("a").title == "Moved"
    assert h.by_google_id("b").deleted_at == NOW
    assert await h.events.list_range(1, NOW, NOW + timedelta(days=30)) == [h.by_google_id("a")]


async def test_last_write_wins(h: Harness) -> None:
    h.api.add_remote("a", **timed("2026-10-12T09:00:00Z", "2026-10-12T10:00:00Z"))
    h.api.add_remote("b", **timed("2026-10-12T11:00:00Z", "2026-10-12T12:00:00Z"))
    await h.sync()

    # Local edits pending push: "a" edited after the remote change, "b" before it.
    for google_id, title, edited_at in (
        ("a", "Local a", NOW + timedelta(minutes=10)),
        ("b", "Local b", NOW - timedelta(minutes=10)),
    ):
        event = h.by_google_id(google_id)
        event.title, event.sync_pending, event.updated_at = title, True, edited_at
    h.api.edit_remote("a", summary="Remote a")
    h.api.edit_remote("b", summary="Remote b")

    assert await h.sync() == 1
    assert h.by_google_id("b").title == "Remote b" and not h.by_google_id("b").sync_pending
    # The newer local edit survived the pull and was then pushed.
    assert h.by_google_id("a").title == "Local a" and not h.by_google_id("a").sync_pending
    assert h.api.live()["a"]["summary"] == "Local a"
    assert h.last.pushed == 1


async def test_remote_delete_versus_newer_local_edit(h: Harness) -> None:
    h.api.add_remote("a", **timed("2026-10-12T09:00:00Z", "2026-10-12T10:00:00Z"))
    await h.sync()
    event = h.by_google_id("a")
    event.sync_pending, event.updated_at = True, NOW + timedelta(minutes=5)
    h.api.cancel_remote("a")

    await h.sync()

    assert event.id is not None
    kept = h.events.events[event.id]
    # The local edit wins: it is created again in Google under a new id.
    assert kept.deleted_at is None and kept.google_event_id == "g1" and not kept.sync_pending
    assert "a" not in h.api.live() and "g1" in h.api.live()


async def test_expired_sync_token_falls_back_to_full_resync(h: Harness) -> None:
    h.api.add_remote("a", **timed("2026-10-12T09:00:00Z", "2026-10-12T10:00:00Z"))
    h.api.add_remote("b", **timed("2026-10-13T09:00:00Z", "2026-10-13T10:00:00Z"))
    await h.sync()

    h.api.expire_tokens()
    del h.api.events["me@example.com"]["b"]  # gone without a trace in the delta
    h.api.add_remote("c", **timed("2026-10-14T09:00:00Z", "2026-10-14T10:00:00Z"))

    assert await h.sync() == 2  # "b" dropped, "c" created ("a" unchanged)
    requests = h.sync_requests()
    assert "syncToken" in requests[-2] and "timeMin" in requests[-1]
    assert h.by_google_id("b").deleted_at == NOW
    assert h.by_google_id("c").deleted_at is None
    assert h.links.links[1].sync_token == f"sync-{h.api.seq}"


async def test_pull_paginates() -> None:
    harness = Harness(FakeGoogleCalendarApi(page_size=2))
    await harness.connect()
    for n in range(5):
        harness.api.add_remote(f"e{n}", **timed("2026-10-12T09:00:00Z", "2026-10-12T10:00:00Z"))

    assert await harness.sync() == 5
    assert [r.get("pageToken") for r in harness.sync_requests()] == [None, "2", "4"]


async def test_remote_changes_flow_back_to_tasks(h: Harness) -> None:
    start = datetime(2026, 10, 12, 9, tzinfo=UTC)
    task = await h.tasks.add(
        Task(
            user_id=1,
            title="Dentist",
            scheduled_start=start,
            scheduled_end=start + timedelta(hours=1),
        )
    )
    await h.events.add(
        CalendarEvent(
            user_id=1,
            title="Dentist",
            start_at=start,
            end_at=start + timedelta(hours=1),
            task_id=task.id,
            google_event_id="t1",
            etag='"old"',
            sync_pending=False,
        )
    )
    h.api.add_remote(
        "t1", summary="Dentist", **timed("2026-10-12T09:00:00Z", "2026-10-12T10:00:00Z")
    )
    await h.sync()  # full sync: etag differs, remote state applied

    h.api.edit_remote("t1", **timed("2026-10-12T15:00:00Z", "2026-10-12T16:00:00Z"))
    await h.sync()
    assert task.id is not None
    moved = h.tasks.tasks[task.id]
    assert moved.scheduled_start == datetime(2026, 10, 12, 15, tzinfo=UTC)

    h.api.cancel_remote("t1")
    await h.sync()
    assert h.tasks.tasks[task.id].scheduled_start is None
