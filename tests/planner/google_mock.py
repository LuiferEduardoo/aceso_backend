"""An httpx MockTransport that imitates the Google OAuth + Calendar endpoints we use."""

from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qs, unquote

import httpx

PRIMARY = "me@example.com"

CALENDARS = [
    {"id": "me@example.com", "summary": "Me", "primary": True, "accessRole": "owner"},
    {"id": "family@group.calendar.google.com", "summary": "Family", "accessRole": "writer"},
    {"id": "holidays@group.v.calendar.google.com", "summary": "Holidays", "accessRole": "reader"},
]


def timed(start: str, end: str) -> dict[str, Any]:
    return {"start": {"dateTime": start}, "end": {"dateTime": end}}


class FakeGoogleCalendarApi:
    """Keeps events per calendar with a change sequence that backs `syncToken`s."""

    def __init__(self, *, refresh_token_on_exchange: bool = True, page_size: int = 250) -> None:
        self.requests: list[httpx.Request] = []
        self.token_grants: list[str] = []
        self.refresh_token_on_exchange = refresh_token_on_exchange
        self.page_size = page_size
        self.events: dict[str, dict[str, dict[str, Any]]] = {}
        self.changed_at: dict[tuple[str, str], int] = {}
        self.seq = 0
        self.expired_tokens: set[str] = set()
        self.now = datetime(2026, 10, 10, 12, tzinfo=UTC)

    # -- helpers for tests ---------------------------------------------------------------

    def _touch(self, calendar_id: str, event: dict[str, Any]) -> dict[str, Any]:
        self.seq += 1
        event["etag"] = f'"etag-{self.seq}"'
        event["updated"] = self.now.isoformat().replace("+00:00", "Z")
        self.events.setdefault(calendar_id, {})[event["id"]] = event
        self.changed_at[(calendar_id, event["id"])] = self.seq
        return event

    def add_remote(
        self, event_id: str, calendar_id: str = PRIMARY, **fields: Any
    ) -> dict[str, Any]:
        event = {"id": event_id, "status": "confirmed", "summary": event_id, **fields}
        return self._touch(calendar_id, event)

    def edit_remote(self, event_id: str, calendar_id: str = PRIMARY, **fields: Any) -> None:
        self._touch(calendar_id, {**self.events[calendar_id][event_id], **fields})

    def cancel_remote(self, event_id: str, calendar_id: str = PRIMARY) -> None:
        self._touch(calendar_id, {"id": event_id, "status": "cancelled"})

    def live(self, calendar_id: str = PRIMARY) -> dict[str, dict[str, Any]]:
        return {
            k: v
            for k, v in self.events.get(calendar_id, {}).items()
            if v.get("status") != "cancelled"
        }

    def expire_tokens(self) -> None:
        self.expired_tokens.update(f"sync-{n}" for n in range(self.seq + 1))

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
        parts = request.url.raw_path.decode().split("?")[0].split("/")
        # /calendar/v3/calendars/{calendarId}/events[/{eventId}]
        if len(parts) >= 6 and parts[3] == "calendars" and parts[5] == "events":
            calendar_id = unquote(parts[4])
            if calendar_id == "primary":
                calendar_id = PRIMARY
            event_id = unquote(parts[6]) if len(parts) > 6 else None
            return self._events(request, calendar_id, event_id)
        return httpx.Response(404, json={"error": {"code": 404}})

    def _events(
        self, request: httpx.Request, calendar_id: str, event_id: str | None
    ) -> httpx.Response:
        if request.method == "GET" and event_id is None:
            return self._list(request, calendar_id)
        return httpx.Response(404, json={"error": {"code": 404}})

    def _list(self, request: httpx.Request, calendar_id: str) -> httpx.Response:
        params = request.url.params
        stored = self.events.get(calendar_id, {})
        sync_token = params.get("syncToken")
        if sync_token is not None:
            if sync_token in self.expired_tokens:
                return httpx.Response(410, json={"error": {"code": 410}})
            since = int(sync_token.removeprefix("sync-"))
            items = [e for e in stored.values() if self.changed_at[(calendar_id, e["id"])] > since]
        else:
            items = [e for e in stored.values() if e.get("status") != "cancelled"]
        items.sort(key=lambda e: self.changed_at[(calendar_id, e["id"])])
        offset = int(params.get("pageToken", "0"))
        page = items[offset : offset + self.page_size]
        body: dict[str, Any] = {"items": page}
        if offset + self.page_size < len(items):
            body["nextPageToken"] = str(offset + self.page_size)
        else:
            body["nextSyncToken"] = f"sync-{self.seq}"
        return httpx.Response(200, json=body)

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
