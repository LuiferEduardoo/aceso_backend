"""Google Calendar API v3 adapter (OAuth2 + calendars + events)."""

from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote, urlencode

import httpx

from aceso.planner.domain.entities import GoogleCalendar, OAuthTokens
from aceso.shared.domain.errors import IntegrationError, InvalidOperationError

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
API_URL = "https://www.googleapis.com/calendar/v3"
SCOPE = "https://www.googleapis.com/auth/calendar"


def _tokens(data: dict[str, Any]) -> OAuthTokens:
    try:
        return OAuthTokens(
            access_token=data["access_token"],
            expires_at=datetime.now(UTC) + timedelta(seconds=int(data["expires_in"])),
            refresh_token=data.get("refresh_token"),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise IntegrationError("Unexpected token response from Google") from exc


def calendar_path(calendar_id: str) -> str:
    return f"{API_URL}/calendars/{quote(calendar_id, safe='')}"


class GoogleCalendarClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri
        self._transport = transport

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
