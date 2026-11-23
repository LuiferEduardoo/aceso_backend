"""An httpx MockTransport that imitates the Google OAuth + Calendar endpoints we use."""

from typing import Any
from urllib.parse import parse_qs

import httpx

CALENDARS = [
    {"id": "me@example.com", "summary": "Me", "primary": True, "accessRole": "owner"},
    {"id": "family@group.calendar.google.com", "summary": "Family", "accessRole": "writer"},
    {"id": "holidays@group.v.calendar.google.com", "summary": "Holidays", "accessRole": "reader"},
]


class FakeGoogleCalendarApi:
    def __init__(self, *, refresh_token_on_exchange: bool = True) -> None:
        self.requests: list[httpx.Request] = []
        self.token_grants: list[str] = []
        self.refresh_token_on_exchange = refresh_token_on_exchange

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.url.host == "oauth2.googleapis.com" and request.url.path == "/token":
            return self._token(parse_qs(request.content.decode()))
        if not request.headers.get("Authorization", "").startswith("Bearer access-"):
            return httpx.Response(401, json={"error": {"code": 401}})
        if request.url.path == "/calendar/v3/users/me/calendarList":
            return httpx.Response(200, json={"items": CALENDARS})
        return httpx.Response(404, json={"error": {"code": 404}})

    def _token(self, form: dict[str, list[str]]) -> httpx.Response:
        grant = form["grant_type"][0]
        self.token_grants.append(grant)
        if form.get("code") == ["bad"]:
            return httpx.Response(400, json={"error": "invalid_grant"})
        body: dict[str, Any] = {
            "access_token": f"access-{len(self.token_grants)}",
            "expires_in": 3599,
            "scope": "https://www.googleapis.com/auth/calendar",
            "token_type": "Bearer",
        }
        # Google only returns a refresh token on the consent exchange, never on refresh.
        if grant == "authorization_code" and self.refresh_token_on_exchange:
            body["refresh_token"] = f"refresh-{len(self.token_grants)}"
        return httpx.Response(200, json=body)
