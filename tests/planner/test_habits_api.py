from httpx import AsyncClient

from tests.conftest import register_and_login


async def test_habit_flow(auth_client: AsyncClient) -> None:
    response = await auth_client.post(
        "/planner/habits",
        json={
            "name": "Stretch",
            "frequency": "weekdays",
            "weekdays": [0, 2, 4],
            "start_date": "2026-10-05",
            "time_of_day": "07:30:00",
            "duration_min": 15,
            "timezone": "Europe/Madrid",
        },
    )
    assert response.status_code == 201, response.text
    habit = response.json()
    assert habit["weekdays"] == [0, 2, 4] and habit["archived_at"] is None
    url = f"/planner/habits/{habit['id']}"

    response = await auth_client.post(f"{url}/logs/2026-10-05")
    assert response.status_code == 200, response.text
    assert response.json()["count"] == 1
    response = await auth_client.post(f"{url}/logs/2026-10-07", json={"count": 2, "note": "ok"})
    assert response.json()["note"] == "ok"

    response = await auth_client.get(
        f"{url}/logs", params={"from": "2026-10-01", "to": "2026-10-31"}
    )
    assert [log["day"] for log in response.json()] == ["2026-10-05", "2026-10-07"]

    response = await auth_client.get(
        f"{url}/stats", params={"from": "2026-10-05", "to": "2026-10-07"}
    )
    assert response.status_code == 200, response.text
    stats = response.json()
    assert stats["streak_unit"] == "day"
    assert (stats["completed"], stats["expected"]) == (2, 2)

    assert (await auth_client.delete(f"{url}/logs/2026-10-07")).status_code == 204
    assert (await auth_client.delete(f"{url}/logs/2026-10-07")).status_code == 404

    response = await auth_client.patch(url, json={"frequency": "times_per_week"})
    assert response.status_code == 422
    response = await auth_client.patch(
        url, json={"frequency": "times_per_week", "times_per_week": 3}
    )
    assert response.json()["weekdays"] == []
    assert (await auth_client.patch(url, json={"name": None})).status_code == 422

    response = await auth_client.post(f"{url}/archive")
    assert response.json()["archived_at"] is not None
    assert (await auth_client.get("/planner/habits")).json() == []
    response = await auth_client.get("/planner/habits", params={"include_archived": True})
    assert len(response.json()) == 1
    assert (await auth_client.post(f"{url}/logs/2026-10-08")).status_code == 422
    await auth_client.post(f"{url}/unarchive")

    assert (await auth_client.delete(url)).status_code == 204
    assert (await auth_client.get(url)).status_code == 404


async def test_habits_are_isolated(auth_client: AsyncClient) -> None:
    habit = (
        await auth_client.post("/planner/habits", json={"name": "Read", "start_date": "2026-10-01"})
    ).json()
    url = f"/planner/habits/{habit['id']}"
    other = await register_and_login(auth_client, "other@example.com")

    assert (await auth_client.get(url, headers=other)).status_code == 404
    assert (await auth_client.patch(url, json={"name": "x"}, headers=other)).status_code == 404
    assert (await auth_client.post(f"{url}/logs/2026-10-02", headers=other)).status_code == 404
    response = await auth_client.get(
        f"{url}/stats", params={"from": "2026-10-01", "to": "2026-10-02"}, headers=other
    )
    assert response.status_code == 404
    assert (await auth_client.delete(url, headers=other)).status_code == 404
    assert (await auth_client.get("/planner/habits", headers=other)).json() == []


async def test_habit_validation(auth_client: AsyncClient) -> None:
    for body in (
        {"name": "x", "start_date": "2026-10-01", "frequency": "weekdays"},
        {"name": "x", "start_date": "2026-10-01", "weekdays": [7]},
        {"name": "x", "start_date": "2026-10-01", "sync_to_calendar": True},
        {"name": "x", "start_date": "2026-10-01", "timezone": "Nowhere/City"},
    ):
        assert (await auth_client.post("/planner/habits", json=body)).status_code == 422
