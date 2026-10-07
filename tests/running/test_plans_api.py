from httpx import AsyncClient

from tests.conftest import register_and_login


async def test_training_plan_flow(auth_client: AsyncClient) -> None:
    response = await auth_client.post(
        "/running/plans",
        json={
            "name": "Half marathon",
            "goal": "Sub 1:45",
            "start_date": "2026-10-05",
            "end_date": "2026-12-20",
            "runs": [
                {"scheduled_date": "2026-10-07", "run_type": "easy", "target_distance_m": 6000},
                {
                    "scheduled_date": "2026-10-05",
                    "run_type": "interval",
                    "description": "6x800m",
                    "target_pace_s_per_km": 270,
                },
            ],
        },
    )
    assert response.status_code == 201, response.text
    plan = response.json()
    assert [r["scheduled_date"] for r in plan["runs"]] == ["2026-10-05", "2026-10-07"]

    response = await auth_client.post(
        f"/running/plans/{plan['id']}/runs",
        json={"scheduled_date": "2026-10-11", "run_type": "long", "target_distance_m": 14000},
    )
    assert response.status_code == 201, response.text
    long_run = response.json()

    response = await auth_client.patch(
        f"/running/planned-runs/{long_run['id']}", json={"target_distance_m": 15000}
    )
    assert response.json()["target_distance_m"] == 15000

    response = await auth_client.get(
        "/running/planned-runs", params={"from": "2026-10-06", "to": "2026-10-12"}
    )
    assert [r["run_type"] for r in response.json()] == ["easy", "long"]

    response = await auth_client.post(
        f"/running/plans/{plan['id']}/runs", json={"scheduled_date": "2027-01-01"}
    )
    assert response.status_code == 422

    assert (await auth_client.delete(f"/running/planned-runs/{long_run['id']}")).status_code == 204
    assert (await auth_client.delete(f"/running/plans/{plan['id']}")).status_code == 204
    assert (await auth_client.get("/running/plans")).json() == []


async def test_plans_are_isolated(auth_client: AsyncClient) -> None:
    plan = (
        await auth_client.post(
            "/running/plans",
            json={"name": "10K", "start_date": "2026-10-01", "end_date": "2026-11-01"},
        )
    ).json()
    other = await register_and_login(auth_client, "other@example.com")
    response = await auth_client.get(f"/running/plans/{plan['id']}", headers=other)
    assert response.status_code == 404
