from httpx import AsyncClient

from tests.conftest import register_and_login


async def test_task_flow(auth_client: AsyncClient) -> None:
    response = await auth_client.post(
        "/planner/tasks",
        json={"title": "Buy shoes", "priority": "high", "due_date": "2026-10-12"},
    )
    assert response.status_code == 201, response.text
    task = response.json()
    assert task["status"] == "todo" and task["completed_at"] is None
    await auth_client.post("/planner/tasks", json={"title": "Later", "due_date": "2026-11-01"})
    await auth_client.post("/planner/tasks", json={"title": "Someday"})

    response = await auth_client.get("/planner/tasks")
    assert [t["title"] for t in response.json()] == ["Buy shoes", "Later", "Someday"]
    response = await auth_client.get(
        "/planner/tasks", params={"due_from": "2026-10-01", "due_to": "2026-10-31"}
    )
    assert [t["title"] for t in response.json()] == ["Buy shoes"]

    url = f"/planner/tasks/{task['id']}"
    response = await auth_client.post(f"{url}/complete")
    assert response.json()["status"] == "done" and response.json()["completed_at"]
    response = await auth_client.get("/planner/tasks", params={"status": "done"})
    assert [t["id"] for t in response.json()] == [task["id"]]
    response = await auth_client.post(f"{url}/reopen")
    assert response.json()["completed_at"] is None

    response = await auth_client.patch(
        url,
        json={
            "scheduled_start": "2026-10-12T09:00:00Z",
            "scheduled_end": "2026-10-12T10:00:00Z",
        },
    )
    assert response.status_code == 200, response.text
    response = await auth_client.patch(url, json={"scheduled_end": None})
    assert response.status_code == 422
    response = await auth_client.patch(url, json={"scheduled_start": "2026-10-12T09:00:00"})
    assert response.status_code == 422  # naive datetime
    assert (await auth_client.patch(url, json={"title": None})).status_code == 422

    assert (await auth_client.delete(url)).status_code == 204
    assert (await auth_client.get(url)).status_code == 404


async def test_tasks_are_isolated(auth_client: AsyncClient) -> None:
    task = (await auth_client.post("/planner/tasks", json={"title": "Mine"})).json()
    url = f"/planner/tasks/{task['id']}"
    other = await register_and_login(auth_client, "other@example.com")

    assert (await auth_client.get(url, headers=other)).status_code == 404
    assert (await auth_client.patch(url, json={"title": "x"}, headers=other)).status_code == 404
    assert (await auth_client.post(f"{url}/complete", headers=other)).status_code == 404
    assert (await auth_client.delete(url, headers=other)).status_code == 404
    assert (await auth_client.get("/planner/tasks", headers=other)).json() == []
