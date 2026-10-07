from urllib.parse import parse_qs, urlparse

from fastapi import FastAPI
from httpx import AsyncClient

from aceso.running.api.deps import get_strava_gateway
from aceso.running.infrastructure.strava import StravaClient
from tests.conftest import register_and_login
from tests.running.strava_mock import FakeStravaApi, strava_activity


async def test_strava_connect_sync_and_list(app: FastAPI, auth_client: AsyncClient) -> None:
    api = FakeStravaApi([strava_activity(1, day=5), strava_activity(2, day=6)])
    app.dependency_overrides[get_strava_gateway] = lambda: StravaClient(
        "cid", "secret", "http://test/running/strava/callback", transport=api.transport()
    )

    assert (await auth_client.post("/running/strava/sync")).status_code == 404

    url = (await auth_client.get("/running/strava/authorize")).json()["authorization_url"]
    state = parse_qs(urlparse(url).query)["state"][0]

    # The callback is a browser redirect: no Authorization header, the state identifies the user.
    response = await auth_client.get(
        "/running/strava/callback",
        params={"code": "abc", "state": state, "scope": "read,activity:read_all"},
        headers={"Authorization": ""},
    )
    assert response.status_code == 200, response.text

    for _ in range(2):  # idempotent
        response = await auth_client.post("/running/strava/sync")
        assert response.status_code == 200, response.text
        assert response.json() == {"synced": 2}

    response = await auth_client.get(
        "/running/activities", params={"from": "2026-10-01", "to": "2026-10-31"}
    )
    activities = response.json()
    assert [a["external_id"] for a in activities] == ["1", "2"]
    assert "raw" not in activities[0]

    response = await auth_client.get(f"/running/activities/{activities[0]['id']}")
    assert response.json()["avg_hr"] == 150.2

    other = await register_and_login(auth_client, "other@example.com")
    response = await auth_client.get(f"/running/activities/{activities[0]['id']}", headers=other)
    assert response.status_code == 404


async def test_strava_callback_rejects_forged_state(auth_client: AsyncClient) -> None:
    response = await auth_client.get(
        "/running/strava/callback", params={"code": "abc", "state": "forged"}
    )
    assert response.status_code == 401
    response = await auth_client.get(
        "/running/strava/callback", params={"error": "access_denied", "state": "x"}
    )
    assert response.status_code == 422


async def test_link_planned_run_with_synced_activity(
    app: FastAPI, auth_client: AsyncClient
) -> None:
    api = FakeStravaApi([strava_activity(1, day=7)])
    app.dependency_overrides[get_strava_gateway] = lambda: StravaClient(
        "cid", "secret", "http://test/cb", transport=api.transport()
    )
    url = (await auth_client.get("/running/strava/authorize")).json()["authorization_url"]
    state = parse_qs(urlparse(url).query)["state"][0]
    await auth_client.get("/running/strava/callback", params={"code": "abc", "state": state})
    await auth_client.post("/running/strava/sync")
    activity = (
        await auth_client.get(
            "/running/activities", params={"from": "2026-10-07", "to": "2026-10-07"}
        )
    ).json()[0]

    plan = (
        await auth_client.post(
            "/running/plans",
            json={
                "name": "10K",
                "start_date": "2026-10-01",
                "end_date": "2026-10-31",
                "runs": [{"scheduled_date": "2026-10-07", "target_distance_m": 10000}],
            },
        )
    ).json()
    run_url = f"/running/planned-runs/{plan['runs'][0]['id']}"

    response = await auth_client.patch(run_url, json={"completed_activity_id": activity["id"]})
    assert response.status_code == 200, response.text
    assert response.json()["completed_activity_id"] == activity["id"]

    response = await auth_client.patch(run_url, json={"completed_activity_id": 999999})
    assert response.status_code == 404

    response = await auth_client.patch(run_url, json={"completed_activity_id": None})
    assert response.json()["completed_activity_id"] is None
