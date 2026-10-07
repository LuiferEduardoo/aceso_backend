from fastapi import FastAPI
from httpx import AsyncClient

from aceso.health.api.deps import get_garmin_provider
from tests.conftest import register_and_login
from tests.health.fakes import FakeProvider

PAYLOAD = {
    "source": "health_connect",
    "daily_summaries": [
        {
            "day": "2026-10-06",
            "steps": 10432,
            "calories_active": 520,
            "calories_total": 2300,
            "active_minutes": 64,
            "resting_hr": 52,
            "avg_hr": 71,
            "max_hr": 160,
            "stress_avg": 28,
        }
    ],
    "samples": [
        {"metric": "heart_rate", "recorded_at": "2026-10-06T08:00:00Z", "value": 61},
        {"metric": "heart_rate", "recorded_at": "2026-10-06T08:01:00Z", "value": 64},
        {"metric": "stress", "recorded_at": "2026-10-06T08:00:00Z", "value": 25},
    ],
    "sleep_sessions": [
        {
            "start_at": "2026-10-05T23:10:00Z",
            "end_at": "2026-10-06T06:40:00Z",
            "deep_s": 5400,
            "light_s": 14400,
            "rem_s": 5400,
            "awake_s": 1800,
            "score": 81,
        }
    ],
}


async def test_ingest_is_idempotent_and_queryable(auth_client: AsyncClient) -> None:
    for _ in range(2):
        response = await auth_client.post("/health/ingest", json=PAYLOAD)
        assert response.status_code == 200, response.text
        assert response.json() == {"daily_summaries": 1, "samples": 3, "sleep_sessions": 1}

    updated = {**PAYLOAD, "daily_summaries": [{"day": "2026-10-06", "steps": 11000}]}
    await auth_client.post("/health/ingest", json=updated)

    summaries = (
        await auth_client.get(
            "/health/summaries", params={"from": "2026-10-01", "to": "2026-10-07"}
        )
    ).json()
    assert len(summaries) == 1
    assert summaries[0]["steps"] == 11000
    assert summaries[0]["source"] == "health_connect"

    samples = (
        await auth_client.get(
            "/health/samples",
            params={
                "metric": "heart_rate",
                "from": "2026-10-06T00:00:00Z",
                "to": "2026-10-07T00:00:00Z",
            },
        )
    ).json()
    assert [s["value"] for s in samples] == [61, 64]

    sleep = (
        await auth_client.get("/health/sleep", params={"from": "2026-10-05", "to": "2026-10-05"})
    ).json()
    assert len(sleep) == 1
    assert sleep[0]["score"] == 81


async def test_sources_are_kept_apart(auth_client: AsyncClient) -> None:
    await auth_client.post("/health/ingest", json=PAYLOAD)
    await auth_client.post("/health/ingest", json={**PAYLOAD, "source": "garmin"})
    params = {"from": "2026-10-06", "to": "2026-10-06"}
    assert len((await auth_client.get("/health/summaries", params=params)).json()) == 2
    response = await auth_client.get("/health/summaries", params={**params, "source": "garmin"})
    assert [s["source"] for s in response.json()] == ["garmin"]


async def test_ingest_validation(auth_client: AsyncClient) -> None:
    bad_sleep = {
        "source": "manual",
        "sleep_sessions": [{"start_at": "2026-10-06T06:00:00Z", "end_at": "2026-10-05T23:00:00Z"}],
    }
    assert (await auth_client.post("/health/ingest", json=bad_sleep)).status_code == 422
    naive = {
        "source": "manual",
        "samples": [{"metric": "heart_rate", "recorded_at": "2026-10-06T08:00:00", "value": 60}],
    }
    assert (await auth_client.post("/health/ingest", json=naive)).status_code == 422
    unknown = {"source": "fitbit"}
    assert (await auth_client.post("/health/ingest", json=unknown)).status_code == 422


async def test_health_data_is_isolated_between_users(auth_client: AsyncClient) -> None:
    await auth_client.post("/health/ingest", json=PAYLOAD)
    other = await register_and_login(auth_client, "other@example.com")
    response = await auth_client.get(
        "/health/summaries", params={"from": "2026-10-01", "to": "2026-10-07"}, headers=other
    )
    assert response.json() == []


async def test_garmin_connect_and_sync(app: FastAPI, auth_client: AsyncClient) -> None:
    app.dependency_overrides[get_garmin_provider] = FakeProvider

    response = await auth_client.post(
        "/health/garmin/sync", params={"from": "2026-10-06", "to": "2026-10-06"}
    )
    assert response.status_code == 404

    response = await auth_client.post(
        "/health/garmin/connect", json={"email": "me@garmin.com", "password": "secret"}
    )
    assert response.status_code == 204

    response = await auth_client.post(
        "/health/garmin/sync", params={"from": "2026-10-06", "to": "2026-10-06"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["daily_summaries"] == 1

    response = await auth_client.get(
        "/health/summaries", params={"from": "2026-10-06", "to": "2026-10-06", "source": "garmin"}
    )
    assert response.json()[0]["steps"] == 9876

    assert (await auth_client.delete("/health/garmin/connect")).status_code == 204
    response = await auth_client.post(
        "/health/garmin/sync", params={"from": "2026-10-06", "to": "2026-10-06"}
    )
    assert response.status_code == 404
