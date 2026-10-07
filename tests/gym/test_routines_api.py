from httpx import AsyncClient

from tests.conftest import register_and_login


async def _exercise(client: AsyncClient, name: str) -> int:
    response = await client.post("/gym/exercises", json={"name": name})
    assert response.status_code == 201
    return response.json()["id"]


async def test_routine_crud(auth_client: AsyncClient) -> None:
    squat = await _exercise(auth_client, "Squat")
    bench = await _exercise(auth_client, "Bench")

    response = await auth_client.post(
        "/gym/routines",
        json={
            "name": "Full body",
            "exercises": [
                {"exercise_id": squat, "target_sets": 5, "target_reps": 5, "target_weight_kg": 80},
                {"exercise_id": bench, "target_sets": 3, "target_reps": 10},
            ],
        },
    )
    assert response.status_code == 201, response.text
    routine = response.json()
    assert [e["position"] for e in routine["exercises"]] == [1, 2]

    response = await auth_client.patch(
        f"/gym/routines/{routine['id']}",
        json={"exercises": [{"exercise_id": bench, "target_sets": 4}, {"exercise_id": squat}]},
    )
    assert response.status_code == 200, response.text
    assert [e["exercise_id"] for e in response.json()["exercises"]] == [bench, squat]
    assert response.json()["name"] == "Full body"

    # Exercises in use cannot be deleted.
    assert (await auth_client.delete(f"/gym/exercises/{squat}")).status_code == 409

    assert (await auth_client.delete(f"/gym/routines/{routine['id']}")).status_code == 204
    assert (await auth_client.get("/gym/routines")).json() == []
    assert (await auth_client.delete(f"/gym/exercises/{squat}")).status_code == 204


async def test_routine_cannot_use_foreign_exercise(auth_client: AsyncClient) -> None:
    other = await register_and_login(auth_client, "other@example.com")
    foreign = (
        await auth_client.post("/gym/exercises", json={"name": "Squat"}, headers=other)
    ).json()["id"]
    response = await auth_client.post(
        "/gym/routines", json={"name": "R", "exercises": [{"exercise_id": foreign}]}
    )
    assert response.status_code == 404


async def test_apply_routine_to_date(auth_client: AsyncClient) -> None:
    squat = await _exercise(auth_client, "Squat")
    routine = (
        await auth_client.post(
            "/gym/routines",
            json={
                "name": "Legs",
                "exercises": [
                    {
                        "exercise_id": squat,
                        "target_sets": 3,
                        "target_reps": 8,
                        "target_weight_kg": 60,
                    }
                ],
            },
        )
    ).json()

    response = await auth_client.post(
        f"/gym/routines/{routine['id']}/apply", json={"scheduled_date": "2026-10-12"}
    )
    assert response.status_code == 201, response.text
    session = response.json()
    assert session["routine_id"] == routine["id"]
    assert session["status"] == "planned"
    sets = session["exercises"][0]["sets"]
    assert [(s["set_number"], s["reps"], s["weight_kg"]) for s in sets] == [
        (1, 8, 60),
        (2, 8, 60),
        (3, 8, 60),
    ]

    # Log the actual values on a pre-filled set.
    response = await auth_client.patch(
        f"/gym/sets/{sets[0]['id']}", json={"reps": 10, "completed": True}
    )
    assert response.json()["reps"] == 10

    response = await auth_client.get(
        "/gym/sessions", params={"from": "2026-10-12", "to": "2026-10-12"}
    )
    assert [s["id"] for s in response.json()] == [session["id"]]

    # Deleting the routine keeps the session history.
    await auth_client.delete(f"/gym/routines/{routine['id']}")
    session = (await auth_client.get(f"/gym/sessions/{session['id']}")).json()
    assert session["routine_id"] is None
