"""An httpx MockTransport that imitates the Strava endpoints we use."""

from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qs

import httpx


def strava_activity(activity_id: int, day: int = 6) -> dict[str, Any]:
    return {
        "id": activity_id,
        "name": f"Run {activity_id}",
        "sport_type": "Run",
        "start_date": f"2026-10-{day:02d}T06:30:00Z",
        "distance": 10000.0,
        "moving_time": 3000,
        "elapsed_time": 3100,
        "total_elevation_gain": 42.0,
        "average_heartrate": 150.2,
        "max_heartrate": 171.0,
        "average_speed": 3.33,
    }


class FakeStravaApi:
    def __init__(self, activities: list[dict[str, Any]] | None = None) -> None:
        self.activities = activities if activities is not None else [strava_activity(1)]
        self.requests: list[httpx.Request] = []
        self.token_grants: list[str] = []

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.url.path == "/oauth/token":
            form = parse_qs(request.content.decode())
            grant = form["grant_type"][0]
            self.token_grants.append(grant)
            if form.get("code") == ["bad"]:
                return httpx.Response(400, json={"message": "Bad Request"})
            return httpx.Response(
                200,
                json={
                    "access_token": f"access-{len(self.token_grants)}",
                    "refresh_token": f"refresh-{len(self.token_grants)}",
                    "expires_at": int((datetime.now(UTC) + timedelta(hours=6)).timestamp()),
                    "athlete": {"id": 99},
                },
            )
        if request.url.path == "/api/v3/athlete/activities":
            if not request.headers.get("Authorization", "").startswith("Bearer access-"):
                return httpx.Response(401, json={"message": "Authorization Error"})
            page = int(request.url.params["page"])
            per_page = int(request.url.params["per_page"])
            chunk = self.activities[(page - 1) * per_page : page * per_page]
            return httpx.Response(200, json=chunk)
        return httpx.Response(404)
