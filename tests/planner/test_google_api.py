from urllib.parse import parse_qs, urlparse

from fastapi import FastAPI
from httpx import AsyncClient, Response

from aceso.planner.api.deps import get_google_gateway
from aceso.planner.infrastructure.google_calendar import GoogleCalendarClient
from tests.conftest import register_and_login
from tests.planner.google_mock import FakeGoogleCalendarApi, timed

FRONTEND = "http://frontend.test"
CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar"


def use_fake_google(app: FastAPI, api: FakeGoogleCalendarApi) -> None:
    app.dependency_overrides[get_google_gateway] = lambda: GoogleCalendarClient(
        "cid", "secret", "http://test/planner/google/callback", transport=api.transport()
    )


async def connect_google(client: AsyncClient, headers: dict[str, str] | None = None) -> None:
    url = (await client.get("/planner/google/authorize", headers=headers)).json()[
        "authorization_url"
    ]
    state = parse_qs(urlparse(url).query)["state"][0]
    # The callback is a browser redirect: no Authorization header, the state identifies the user.
    response = await client.get(
        "/planner/google/callback",
        params={"code": "abc", "state": state, "scope": CALENDAR_SCOPE},
        headers={"Authorization": ""},
    )
    assert response.status_code == 303, response.text
    assert response.headers["location"] == f"{FRONTEND}/planner/agenda?google=connected"


def _redirect_reason(response: Response) -> str:
    assert response.status_code == 303, response.text
    location = urlparse(response.headers["location"])
    assert f"{location.scheme}://{location.netloc}{location.path}" == f"{FRONTEND}/planner/agenda"
    query = parse_qs(location.query)
    assert query["google"] == ["error"]
    assert set(query) == {"google", "reason"}
    return query["reason"][0]


async def test_google_connect_select_and_disconnect(app: FastAPI, auth_client: AsyncClient) -> None:
    use_fake_google(app, FakeGoogleCalendarApi())
    assert (await auth_client.get("/planner/google/calendars")).status_code == 404

    await connect_google(auth_client)

    response = await auth_client.get("/planner/google/calendars")
    assert response.status_code == 200, response.text
    assert [c["summary"] for c in response.json()] == ["Me", "Family", "Holidays"]

    response = await auth_client.put(
        "/planner/google/calendar", json={"calendar_id": "family@group.calendar.google.com"}
    )
    assert response.status_code == 200, response.text
    assert response.json() == {
        "calendar_id": "family@group.calendar.google.com",
        "last_synced_at": None,
    }
    response = await auth_client.put(
        "/planner/google/calendar", json={"calendar_id": "holidays@group.v.calendar.google.com"}
    )
    assert response.status_code == 422

    # Another user is not connected, whatever this user did.
    other = await register_and_login(auth_client, "other@example.com")
    assert (await auth_client.get("/planner/google/calendars", headers=other)).status_code == 404
    response = await auth_client.put(
        "/planner/google/calendar", json={"calendar_id": "me@example.com"}, headers=other
    )
    assert response.status_code == 404

    assert (await auth_client.delete("/planner/google")).status_code == 204
    assert (await auth_client.get("/planner/google/calendars")).status_code == 404


async def test_google_callback_redirects_failures_with_a_reason(
    app: FastAPI, auth_client: AsyncClient
) -> None:
    use_fake_google(app, FakeGoogleCalendarApi())
    url = (await auth_client.get("/planner/google/authorize")).json()["authorization_url"]
    state = parse_qs(urlparse(url).query)["state"][0]

    async def callback(**params: str) -> Response:
        return await auth_client.get(
            "/planner/google/callback", params=params, headers={"Authorization": ""}
        )

    response = await callback(error="access_denied", state=state)
    assert _redirect_reason(response) == "access_denied"
    # Google's own error text is never echoed back.
    response = await callback(error="server_error<script>", state=state)
    assert _redirect_reason(response) == "authorization_failed"
    assert _redirect_reason(await callback(state=state)) == "authorization_failed"
    assert _redirect_reason(await callback(code="abc")) == "invalid_state"
    response = await callback(code="abc", state="forged", scope=CALENDAR_SCOPE)
    assert _redirect_reason(response) == "invalid_state"
    response = await callback(code="abc", state=state, scope="email")
    assert _redirect_reason(response) == "missing_scope"
    response = await callback(code="bad", state=state, scope=CALENDAR_SCOPE)
    assert _redirect_reason(response) == "exchange_failed"
    assert "bad" not in response.headers["location"]

    # None of the failures connected the account.
    response = await auth_client.get("/planner/google/status")
    assert response.json()["connected"] is False


async def test_google_status(app: FastAPI, auth_client: AsyncClient) -> None:
    api = FakeGoogleCalendarApi()
    use_fake_google(app, api)
    disconnected = {"connected": False, "calendar_id": None, "last_synced_at": None}
    response = await auth_client.get("/planner/google/status")
    assert response.status_code == 200, response.text
    assert response.json() == disconnected

    await connect_google(auth_client)
    response = await auth_client.get("/planner/google/status")
    assert response.json() == {"connected": True, "calendar_id": "primary", "last_synced_at": None}

    await auth_client.put(
        "/planner/google/calendar", json={"calendar_id": "family@group.calendar.google.com"}
    )
    assert (await auth_client.post("/planner/google/sync")).status_code == 200
    status = (await auth_client.get("/planner/google/status")).json()
    assert status["connected"] is True
    assert status["calendar_id"] == "family@group.calendar.google.com"
    assert status["last_synced_at"] is not None
    # The status never talks to Google.
    calls = len(api.requests)
    await auth_client.get("/planner/google/status")
    assert len(api.requests) == calls

    other = await register_and_login(auth_client, "other@example.com")
    response = await auth_client.get("/planner/google/status", headers=other)
    assert response.json() == disconnected

    assert (await auth_client.delete("/planner/google")).status_code == 204
    assert (await auth_client.get("/planner/google/status")).json() == disconnected

    response = await auth_client.get("/planner/google/status", headers={"Authorization": ""})
    assert response.status_code == 401


async def test_google_pull_into_agenda(app: FastAPI, auth_client: AsyncClient) -> None:
    api = FakeGoogleCalendarApi()
    use_fake_google(app, api)
    assert (await auth_client.post("/planner/google/sync")).status_code == 404

    await connect_google(auth_client)
    api.add_remote(
        "remote-1",
        summary="Lunch with Ana",
        location="Café",
        **timed("2026-10-12T12:00:00Z", "2026-10-12T13:00:00Z"),
    )

    response = await auth_client.post("/planner/google/sync")
    assert response.status_code == 200, response.text
    assert response.json()["pulled"] == 1

    response = await auth_client.get(
        "/planner/agenda", params={"from": "2026-10-12", "to": "2026-10-12"}
    )
    [event] = response.json()[0]["events"]
    assert event["source"] == "google" and event["title"] == "Lunch with Ana"

    api.edit_remote("remote-1", summary="Lunch with Ana & Leo")
    assert (await auth_client.post("/planner/google/sync")).json()["pulled"] == 1
    response = await auth_client.get(f"/planner/events/{event['id']}")
    assert response.json()["title"] == "Lunch with Ana & Leo"

    other = await register_and_login(auth_client, "other@example.com")
    assert (await auth_client.post("/planner/google/sync", headers=other)).status_code == 404
    assert (
        await auth_client.get(f"/planner/events/{event['id']}", headers=other)
    ).status_code == 404

    api.cancel_remote("remote-1")
    await auth_client.post("/planner/google/sync")
    assert (await auth_client.get(f"/planner/events/{event['id']}")).status_code == 404


async def test_two_way_sync_of_a_scheduled_task(app: FastAPI, auth_client: AsyncClient) -> None:
    api = FakeGoogleCalendarApi()
    use_fake_google(app, api)
    await connect_google(auth_client)
    task = (
        await auth_client.post(
            "/planner/tasks",
            json={
                "title": "Dentist",
                "scheduled_start": "2026-10-12T09:00:00Z",
                "scheduled_end": "2026-10-12T10:00:00Z",
            },
        )
    ).json()
    await auth_client.post(
        "/planner/habits",
        json={
            "name": "Stretch",
            "start_date": "2026-10-12",
            "time_of_day": "07:00:00",
            "sync_to_calendar": True,
        },
    )

    response = await auth_client.post("/planner/google/sync")
    assert response.status_code == 200, response.text
    assert response.json() == {"pulled": 0, "pushed": 2, "deleted": 0}
    by_ref = {e["extendedProperties"]["private"]["aceso_ref"]: e for e in api.live().values()}
    remote_task = by_ref[f"task:{task['id']}"]
    assert remote_task["summary"] == "Dentist"
    assert any(e.get("recurrence") == ["RRULE:FREQ=DAILY"] for e in by_ref.values())

    # Edited in Google: the next sync moves the task and its event.
    api.edit_remote(
        remote_task["id"],
        summary="Dentist (moved)",
        **timed("2026-10-13T15:00:00Z", "2026-10-13T16:00:00Z"),
    )
    response = await auth_client.post("/planner/google/sync")
    assert response.json() == {"pulled": 1, "pushed": 0, "deleted": 0}
    response = await auth_client.get(
        "/planner/agenda", params={"from": "2026-10-13", "to": "2026-10-13"}
    )
    day = response.json()[0]
    assert [t["title"] for t in day["tasks"]] == ["Dentist (moved)"]
    assert day["events"][0]["start_at"] == "2026-10-13T15:00:00Z"

    # Deleted locally: removed from Google on the next sync.
    assert (await auth_client.delete(f"/planner/tasks/{task['id']}")).status_code == 204
    response = await auth_client.post("/planner/google/sync")
    assert response.json()["deleted"] == 1
    assert remote_task["id"] not in api.live()
