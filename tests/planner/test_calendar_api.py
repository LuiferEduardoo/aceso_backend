from httpx import AsyncClient

from tests.conftest import register_and_login


async def test_event_flow(auth_client: AsyncClient) -> None:
    response = await auth_client.post(
        "/planner/events",
        json={
            "title": "Physio",
            "location": "Clinic",
            "start_at": "2026-10-12T09:00:00Z",
            "end_at": "2026-10-12T10:00:00Z",
        },
    )
    assert response.status_code == 201, response.text
    event = response.json()
    assert event["source"] == "local" and event["sync_pending"] is True
    url = f"/planner/events/{event['id']}"

    response = await auth_client.post(
        "/planner/events",
        json={
            "title": "Trip",
            "all_day": True,
            "start_at": "2026-10-13T00:00:00Z",
            "end_at": "2026-10-15T00:00:00Z",
        },
    )
    assert response.json()["end_at"] == "2026-10-15T00:00:00Z"

    response = await auth_client.get(
        "/planner/events", params={"from": "2026-10-12", "to": "2026-10-12"}
    )
    assert [e["title"] for e in response.json()] == ["Physio"]

    response = await auth_client.patch(url, json={"end_at": "2026-10-12T08:00:00Z"})
    assert response.status_code == 422
    response = await auth_client.patch(url, json={"title": "Physio (moved)"})
    assert response.json()["title"] == "Physio (moved)"

    assert (await auth_client.delete(url)).status_code == 204
    assert (await auth_client.get(url)).status_code == 404


async def test_agenda_and_task_linked_event(auth_client: AsyncClient) -> None:
    task = (
        await auth_client.post(
            "/planner/tasks",
            json={
                "title": "Call bank",
                "scheduled_start": "2026-10-12T11:00:00Z",
                "scheduled_end": "2026-10-12T11:30:00Z",
            },
        )
    ).json()
    await auth_client.post("/planner/tasks", json={"title": "Taxes", "due_date": "2026-10-13"})
    habit = (
        await auth_client.post("/planner/habits", json={"name": "Walk", "start_date": "2026-10-01"})
    ).json()
    await auth_client.post(f"/planner/habits/{habit['id']}/logs/2026-10-12")

    response = await auth_client.get(
        "/planner/agenda", params={"from": "2026-10-12", "to": "2026-10-13"}
    )
    assert response.status_code == 200, response.text
    monday, tuesday = response.json()
    assert monday["date"] == "2026-10-12"
    [linked] = monday["events"]
    assert linked["task_id"] == task["id"] and linked["title"] == "Call bank"
    assert [t["title"] for t in monday["tasks"]] == ["Call bank"]
    assert monday["habits"][0]["completed"] is True
    assert [t["title"] for t in tuesday["tasks"]] == ["Taxes"]
    assert tuesday["habits"][0]["count"] == 0

    # The linked event is managed through its task.
    event_url = f"/planner/events/{linked['id']}"
    assert (await auth_client.patch(event_url, json={"title": "x"})).status_code == 422
    await auth_client.patch(
        f"/planner/tasks/{task['id']}", json={"scheduled_start": None, "scheduled_end": None}
    )
    assert (await auth_client.get(event_url)).status_code == 404

    response = await auth_client.get(
        "/planner/agenda", params={"from": "2026-10-13", "to": "2026-10-12"}
    )
    assert response.status_code == 422


async def test_events_are_isolated(auth_client: AsyncClient) -> None:
    event = (
        await auth_client.post(
            "/planner/events",
            json={
                "title": "Mine",
                "start_at": "2026-10-12T09:00:00Z",
                "end_at": "2026-10-12T10:00:00Z",
            },
        )
    ).json()
    url = f"/planner/events/{event['id']}"
    other = await register_and_login(auth_client, "other@example.com")

    assert (await auth_client.get(url, headers=other)).status_code == 404
    assert (await auth_client.patch(url, json={"title": "x"}, headers=other)).status_code == 404
    assert (await auth_client.delete(url, headers=other)).status_code == 404
    response = await auth_client.get(
        "/planner/agenda", params={"from": "2026-10-12", "to": "2026-10-12"}, headers=other
    )
    assert response.json()[0]["events"] == []
