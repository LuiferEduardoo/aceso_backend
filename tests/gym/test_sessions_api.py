from httpx import AsyncClient

from tests.conftest import register_and_login
from tests.gym.factories import exercise_payload


async def _exercise(client: AsyncClient, name: str) -> int:
    return (await client.post("/gym/exercises", json=exercise_payload(name))).json()["id"]


async def test_log_workout_with_sets_and_intervals(auth_client: AsyncClient) -> None:
    climber = await _exercise(auth_client, "Stair climber")
    pushups = await _exercise(auth_client, "Push-ups")

    response = await auth_client.post("/gym/sessions", json={"scheduled_date": "2026-10-07"})
    assert response.status_code == 201, response.text
    session = response.json()

    response = await auth_client.post(
        f"/gym/sessions/{session['id']}/exercises", json={"exercise_id": climber}
    )
    assert response.status_code == 201, response.text
    climber_item = response.json()

    response = await auth_client.post(
        f"/gym/session-exercises/{climber_item['id']}/sets",
        json={
            "completed": True,
            "intervals": [{"duration_s": 60, "level": 5}, {"duration_s": 60, "level": 10}],
        },
    )
    assert response.status_code == 201, response.text
    climber_set = response.json()
    assert climber_set["duration_s"] == 120
    assert [i["level"] for i in climber_set["intervals"]] == [5, 10]

    pushups_item = (
        await auth_client.post(
            f"/gym/sessions/{session['id']}/exercises", json={"exercise_id": pushups}
        )
    ).json()
    response = await auth_client.post(
        f"/gym/session-exercises/{pushups_item['id']}/sets",
        json={"reps": 15, "added_weight_kg": 10, "rpe": 8},
    )
    assert response.status_code == 201, response.text
    pushup_set = response.json()

    response = await auth_client.patch(
        f"/gym/sets/{pushup_set['id']}", json={"reps": 12, "completed": True}
    )
    assert response.json()["reps"] == 12

    response = await auth_client.patch(
        f"/gym/sessions/{session['id']}",
        json={
            "status": "completed",
            "started_at": "2026-10-07T18:00:00Z",
            "finished_at": "2026-10-07T19:00:00Z",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "completed"
    assert [len(e["sets"]) for e in body["exercises"]] == [1, 1]

    response = await auth_client.get(
        "/gym/sessions", params={"from": "2026-10-01", "to": "2026-10-31"}
    )
    assert [s["id"] for s in response.json()] == [session["id"]]
    assert response.json()[0]["exercises"][0]["sets"][0]["intervals"][1]["level"] == 10

    assert (await auth_client.delete(f"/gym/sets/{climber_set['id']}")).status_code == 204
    response = await auth_client.delete(f"/gym/session-exercises/{pushups_item['id']}")
    assert response.status_code == 204
    session = (await auth_client.get(f"/gym/sessions/{session['id']}")).json()
    assert [len(e["sets"]) for e in session["exercises"]] == [0]

    assert (await auth_client.delete(f"/gym/sessions/{session['id']}")).status_code == 204
    assert (await auth_client.get(f"/gym/sessions/{session['id']}")).status_code == 404


async def test_create_session_with_nested_exercises(auth_client: AsyncClient) -> None:
    treadmill = await _exercise(auth_client, "Treadmill")
    response = await auth_client.post(
        "/gym/sessions",
        json={
            "scheduled_date": "2026-10-08",
            "exercises": [
                {
                    "exercise_id": treadmill,
                    "sets": [
                        {
                            "intervals": [
                                {"duration_s": 300, "speed": 6, "incline_pct": 8},
                                {"duration_s": 120, "speed": 10, "incline_pct": 1},
                            ]
                        }
                    ],
                }
            ],
        },
    )
    assert response.status_code == 201, response.text
    exercise_set = response.json()["exercises"][0]["sets"][0]
    assert exercise_set["duration_s"] == 420
    assert exercise_set["intervals"][0]["incline_pct"] == 8


async def test_invalid_payloads(auth_client: AsyncClient) -> None:
    exercise = await _exercise(auth_client, "Squat")
    session = (
        await auth_client.post("/gym/sessions", json={"scheduled_date": "2026-10-07"})
    ).json()
    item = (
        await auth_client.post(
            f"/gym/sessions/{session['id']}/exercises", json={"exercise_id": exercise}
        )
    ).json()
    url = f"/gym/session-exercises/{item['id']}/sets"
    assert (await auth_client.post(url, json={"rpe": 7})).status_code == 422
    assert (await auth_client.post(url, json={"intervals": [{"level": 3}]})).status_code == 422
    response = await auth_client.get(
        "/gym/sessions", params={"from": "2026-10-10", "to": "2026-10-01"}
    )
    assert response.status_code == 422


async def test_sessions_are_isolated_between_users(auth_client: AsyncClient) -> None:
    session = (
        await auth_client.post("/gym/sessions", json={"scheduled_date": "2026-10-07"})
    ).json()
    other = await register_and_login(auth_client, "other@example.com")
    assert (
        await auth_client.get(f"/gym/sessions/{session['id']}", headers=other)
    ).status_code == 404
    response = await auth_client.get(
        "/gym/sessions", params={"from": "2026-10-01", "to": "2026-10-31"}, headers=other
    )
    assert response.json() == []
