"""Strava API v3 adapter (OAuth2 + activities)."""

from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

import httpx

from aceso.running.domain.entities import Activity, ActivitySource, OAuthTokens
from aceso.shared.domain.errors import IntegrationError, InvalidOperationError

AUTHORIZE_URL = "https://www.strava.com/oauth/authorize"
TOKEN_URL = "https://www.strava.com/oauth/token"
API_URL = "https://www.strava.com/api/v3"
SCOPES = "read,activity:read_all"


def _tokens(data: dict[str, Any]) -> OAuthTokens:
    try:
        return OAuthTokens(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_at=datetime.fromtimestamp(data["expires_at"], tz=UTC),
            athlete_id=(data.get("athlete") or {}).get("id"),
        )
    except (KeyError, TypeError) as exc:
        raise IntegrationError("Unexpected token response from Strava") from exc


def map_activity(data: dict[str, Any]) -> Activity:
    return Activity(
        source=ActivitySource.STRAVA,
        external_id=str(data["id"]),
        sport_type=data.get("sport_type") or data.get("type") or "Unknown",
        name=data.get("name"),
        start_at=datetime.fromisoformat(data["start_date"].replace("Z", "+00:00")),
        distance_m=data.get("distance"),
        moving_time_s=data.get("moving_time"),
        elapsed_time_s=data.get("elapsed_time"),
        elevation_gain_m=data.get("total_elevation_gain"),
        avg_hr=data.get("average_heartrate"),
        max_hr=data.get("max_heartrate"),
        avg_speed=data.get("average_speed"),
        calories=data.get("calories"),
        raw=data,
    )


class StravaClient:
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
            raise IntegrationError("Strava is not configured (STRAVA_CLIENT_ID/SECRET)")

    def authorization_url(self, state: str) -> str:
        self._require_config()
        query = urlencode(
            {
                "client_id": self._client_id,
                "redirect_uri": self._redirect_uri,
                "response_type": "code",
                "approval_prompt": "auto",
                "scope": SCOPES,
                "state": state,
            }
        )
        return f"{AUTHORIZE_URL}?{query}"

    async def exchange_code(self, code: str) -> OAuthTokens:
        return _tokens(
            await self._token_request({"grant_type": "authorization_code", "code": code})
        )

    async def refresh(self, refresh_token: str) -> OAuthTokens:
        return _tokens(
            await self._token_request(
                {"grant_type": "refresh_token", "refresh_token": refresh_token}
            )
        )

    async def list_activities(
        self, access_token: str, *, after: datetime | None, page: int, per_page: int
    ) -> list[Activity]:
        params: dict[str, Any] = {"page": page, "per_page": per_page}
        if after is not None:
            params["after"] = int(after.timestamp())
        data = await self._request(
            "GET",
            f"{API_URL}/athlete/activities",
            params=params,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        return [map_activity(item) for item in data]

    async def _token_request(self, data: dict[str, str]) -> dict[str, Any]:
        self._require_config()
        payload = {"client_id": self._client_id, "client_secret": self._client_secret, **data}
        return await self._request("POST", TOKEN_URL, data=payload)

    async def _request(self, method: str, url: str, **kwargs: Any) -> Any:
        try:
            async with httpx.AsyncClient(transport=self._transport, timeout=20) as client:
                response = await client.request(method, url, **kwargs)
        except httpx.HTTPError as exc:
            raise IntegrationError("Could not reach Strava") from exc
        if response.status_code in (400, 401, 403):
            raise InvalidOperationError("Strava rejected the authorization; connect again")
        if response.status_code == 429:
            raise IntegrationError("Strava rate limit reached, try again later")
        if response.is_error:
            raise IntegrationError(f"Strava error ({response.status_code})")
        return response.json()
