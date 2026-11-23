"""Google Calendar API v3 adapter (OAuth2 + calendars + events)."""

from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from urllib.parse import quote, urlencode
from zoneinfo import ZoneInfo

import httpx

from aceso.planner.domain.entities import (
    ACESO_REF_KEY,
    DEFAULT_TIMEZONE,
    EventDraft,
    GoogleCalendar,
    OAuthTokens,
    RemoteEvent,
    RemoteEventPage,
)
from aceso.planner.domain.errors import RemoteEventMissingError, SyncTokenExpiredError
from aceso.shared.domain.errors import IntegrationError, InvalidOperationError, NotFoundError

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
API_URL = "https://www.googleapis.com/calendar/v3"
SCOPE = "https://www.googleapis.com/auth/calendar"
PAGE_SIZE = 250


def _tokens(data: dict[str, Any]) -> OAuthTokens:
    try:
        return OAuthTokens(
            access_token=data["access_token"],
            expires_at=datetime.now(UTC) + timedelta(seconds=int(data["expires_in"])),
            refresh_token=data.get("refresh_token"),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise IntegrationError("Unexpected token response from Google") from exc


def _parse_time(value: dict[str, Any] | None, tz: ZoneInfo) -> tuple[datetime | None, bool]:
    """Google gives `dateTime` for timed events and `date` for all-day ones (days in `tz`)."""
    if not value:
        return None, False
    if "dateTime" in value:
        return datetime.fromisoformat(value["dateTime"]).astimezone(UTC), False
    if "date" in value:
        local = datetime.combine(date.fromisoformat(value["date"]), time.min, tzinfo=tz)
        return local.astimezone(UTC), True
    return None, False


def map_remote_event(data: dict[str, Any], timezone: str = DEFAULT_TIMEZONE) -> RemoteEvent:
    tz = ZoneInfo(timezone)
    start_at, all_day = _parse_time(data.get("start"), tz)
    end_at, _ = _parse_time(data.get("end"), tz)
    private = (data.get("extendedProperties") or {}).get("private") or {}
    updated = data.get("updated")
    return RemoteEvent(
        id=data["id"],
        status=data.get("status", "confirmed"),
        updated=datetime.fromisoformat(updated) if updated else None,
        etag=data.get("etag"),
        title=(data.get("summary") or "")[:1000],
        description=data.get("description"),
        location=data.get("location"),
        start_at=start_at,
        end_at=end_at,
        all_day=all_day,
        aceso_ref=private.get(ACESO_REF_KEY),
        recurring_event_id=data.get("recurringEventId"),
    )


def _format_time(moment: datetime, all_day: bool, timezone: str) -> dict[str, str]:
    if all_day:
        return {"date": moment.astimezone(ZoneInfo(timezone)).date().isoformat()}
    return {"dateTime": moment.astimezone(ZoneInfo(timezone)).isoformat(), "timeZone": timezone}


def draft_body(draft: EventDraft) -> dict[str, Any]:
    body: dict[str, Any] = {
        "summary": draft.title,
        "description": draft.description or "",
        "location": draft.location or "",
        "start": _format_time(draft.start_at, draft.all_day, draft.timezone),
        "end": _format_time(draft.end_at, draft.all_day, draft.timezone),
        "extendedProperties": {"private": {ACESO_REF_KEY: draft.aceso_ref}},
    }
    if draft.recurrence:
        body["recurrence"] = list(draft.recurrence)
    return body


def calendar_path(calendar_id: str) -> str:
    return f"{API_URL}/calendars/{quote(calendar_id, safe='')}"


class GoogleCalendarClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        transport: httpx.AsyncBaseTransport | None = None,
        timezone: str = DEFAULT_TIMEZONE,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri
        self._transport = transport
        self._timezone = timezone  # Zone whose days Google's all-day `date` values denote.

    def _require_config(self) -> None:
        if not self._client_id or not self._client_secret:
            raise IntegrationError("Google is not configured (GOOGLE_CLIENT_ID/SECRET)")

    def authorization_url(self, state: str) -> str:
        self._require_config()
        query = urlencode(
            {
                "client_id": self._client_id,
                "redirect_uri": self._redirect_uri,
                "response_type": "code",
                "scope": SCOPE,
                "access_type": "offline",
                "prompt": "consent",
                "include_granted_scopes": "true",
                "state": state,
            }
        )
        return f"{AUTHORIZE_URL}?{query}"

    async def exchange_code(self, code: str) -> OAuthTokens:
        return _tokens(
            await self._token_request(
                {
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": self._redirect_uri,
                }
            )
        )

    async def refresh(self, refresh_token: str) -> OAuthTokens:
        return _tokens(
            await self._token_request(
                {"grant_type": "refresh_token", "refresh_token": refresh_token}
            )
        )

    async def list_calendars(self, access_token: str) -> list[GoogleCalendar]:
        calendars: list[GoogleCalendar] = []
        page_token: str | None = None
        while True:
            params = {"pageToken": page_token} if page_token else {}
            data = self._check(
                await self._send(
                    "GET",
                    f"{API_URL}/users/me/calendarList",
                    access_token=access_token,
                    params=params,
                )
            )
            calendars.extend(
                GoogleCalendar(
                    id=item["id"],
                    summary=item.get("summaryOverride") or item.get("summary") or item["id"],
                    primary=bool(item.get("primary")),
                    access_role=item.get("accessRole", "reader"),
                )
                for item in data.get("items", [])
            )
            page_token = data.get("nextPageToken")
            if not page_token:
                return calendars

    async def list_events(
        self,
        access_token: str,
        calendar_id: str,
        *,
        sync_token: str | None = None,
        time_min: datetime | None = None,
        time_max: datetime | None = None,
        page_token: str | None = None,
    ) -> RemoteEventPage:
        params: dict[str, Any] = {"singleEvents": "true", "maxResults": PAGE_SIZE}
        if sync_token:
            params["syncToken"] = sync_token
        else:
            if time_min is not None:
                params["timeMin"] = time_min.isoformat()
            if time_max is not None:
                params["timeMax"] = time_max.isoformat()
        if page_token:
            params["pageToken"] = page_token
        response = await self._send(
            "GET",
            f"{calendar_path(calendar_id)}/events",
            access_token=access_token,
            params=params,
        )
        if response.status_code == 410:
            raise SyncTokenExpiredError("Google sync token expired; a full sync is needed")
        if response.status_code == 404:
            raise NotFoundError("Google calendar not found; choose another one")
        data = self._check(response)
        return RemoteEventPage(
            events=[map_remote_event(item, self._timezone) for item in data.get("items", [])],
            next_page_token=data.get("nextPageToken"),
            next_sync_token=data.get("nextSyncToken"),
        )

    async def insert_event(
        self, access_token: str, calendar_id: str, draft: EventDraft
    ) -> RemoteEvent:
        response = await self._send(
            "POST",
            f"{calendar_path(calendar_id)}/events",
            access_token=access_token,
            json=draft_body(draft),
        )
        return map_remote_event(self._check(response), self._timezone)

    async def patch_event(
        self, access_token: str, calendar_id: str, event_id: str, draft: EventDraft
    ) -> RemoteEvent:
        response = await self._send(
            "PATCH",
            f"{calendar_path(calendar_id)}/events/{quote(event_id, safe='')}",
            access_token=access_token,
            json=draft_body(draft),
        )
        if response.status_code in (404, 410):
            raise RemoteEventMissingError("Google event no longer exists")
        return map_remote_event(self._check(response), self._timezone)

    async def delete_event(self, access_token: str, calendar_id: str, event_id: str) -> None:
        response = await self._send(
            "DELETE",
            f"{calendar_path(calendar_id)}/events/{quote(event_id, safe='')}",
            access_token=access_token,
        )
        if response.status_code not in (404, 410):
            self._check(response)

    async def _token_request(self, data: dict[str, str]) -> dict[str, Any]:
        self._require_config()
        payload = {"client_id": self._client_id, "client_secret": self._client_secret, **data}
        return self._check(await self._send("POST", TOKEN_URL, data=payload))

    async def _send(
        self, method: str, url: str, access_token: str | None = None, **kwargs: Any
    ) -> httpx.Response:
        if access_token is not None:
            kwargs["headers"] = {"Authorization": f"Bearer {access_token}"}
        try:
            async with httpx.AsyncClient(transport=self._transport, timeout=20) as client:
                return await client.request(method, url, **kwargs)
        except httpx.HTTPError as exc:
            raise IntegrationError("Could not reach Google") from exc

    @staticmethod
    def _check(response: httpx.Response) -> Any:
        if response.status_code in (400, 401, 403):
            raise InvalidOperationError("Google rejected the request; connect again")
        if response.status_code == 429:
            raise IntegrationError("Google rate limit reached, try again later")
        if response.is_error:
            raise IntegrationError(f"Google error ({response.status_code})")
        return response.json() if response.content else {}
