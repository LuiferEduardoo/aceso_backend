from urllib.parse import parse_qs, urlparse

from fastapi import FastAPI
from httpx import AsyncClient

from aceso.planner.api.deps import get_google_gateway
from aceso.planner.infrastructure.google_calendar import GoogleCalendarClient
from tests.conftest import register_and_login
from tests.planner.google_mock import FakeGoogleCalendarApi


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
        params={"code": "abc", "state": state, "scope": "https://www.googleapis.com/auth/calendar"},
        headers={"Authorization": ""},
    )
    assert response.status_code == 200, response.text


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


async def test_google_callback_rejects_forged_state(auth_client: AsyncClient) -> None:
    response = await auth_client.get(
        "/planner/google/callback", params={"code": "abc", "state": "forged"}
    )
    assert response.status_code == 401
    response = await auth_client.get(
        "/planner/google/callback", params={"error": "access_denied", "state": "x"}
    )
    assert response.status_code == 422
