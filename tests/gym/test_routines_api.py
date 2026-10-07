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
