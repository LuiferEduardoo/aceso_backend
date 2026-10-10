import pytest
from httpx import AsyncClient

from tests.conftest import register_and_login
from tests.gym.factories import exercise_payload


async def test_exercise_crud(auth_client: AsyncClient) -> None:
    response = await auth_client.post(
        "/gym/exercises",
        json=exercise_payload(
            "Stair climber",
            muscle_group="cardio",
            secondary_muscles=["glutes", "calves"],
            equipment="cardio_machine",
            exercise_type="cardio",
            instructions="Level 5-10",
        ),
    )
    assert response.status_code == 201, response.text
    exercise = response.json()
    assert exercise["muscle_group"] == "cardio"
    assert exercise["secondary_muscles"] == ["glutes", "calves"]
    assert exercise["equipment"] == "cardio_machine"
    assert exercise["exercise_type"] == "cardio"
    assert exercise["instructions"] == "Level 5-10"
    assert exercise["image_url"] is None

    response = await auth_client.patch(
        f"/gym/exercises/{exercise['id']}",
        json={"instructions": "Level 8", "secondary_muscles": ["quadriceps"]},
    )
    assert response.status_code == 200, response.text
    assert response.json()["instructions"] == "Level 8"
    assert response.json()["secondary_muscles"] == ["quadriceps"]
    fetched = (await auth_client.get(f"/gym/exercises/{exercise['id']}")).json()
    assert fetched["secondary_muscles"] == ["quadriceps"]
    assert fetched["equipment"] == "cardio_machine"

    response = await auth_client.get("/gym/exercises")
    assert [e["name"] for e in response.json()] == ["Stair climber"]

    response = await auth_client.delete(f"/gym/exercises/{exercise['id']}")
    assert response.status_code == 204
    assert (await auth_client.get(f"/gym/exercises/{exercise['id']}")).status_code == 404


async def test_duplicate_exercise_name_conflicts(auth_client: AsyncClient) -> None:
    assert (
        await auth_client.post("/gym/exercises", json=exercise_payload("Squat"))
    ).status_code == 201
    assert (
        await auth_client.post("/gym/exercises", json=exercise_payload("squat"))
    ).status_code == 409


async def test_photo_upload_download_and_delete(auth_client: AsyncClient) -> None:
    exercise = (await auth_client.post("/gym/exercises", json=exercise_payload("Squat"))).json()
    url = f"/gym/exercises/{exercise['id']}/photo"

    response = await auth_client.put(url, files={"photo": ("p.png", b"\x89PNG-data", "image/png")})
    assert response.status_code == 200
    assert response.json()["image_url"] == url

    response = await auth_client.get(url)
    assert response.status_code == 200
    assert response.content == b"\x89PNG-data"
    assert response.headers["content-type"] == "image/png"

    response = await auth_client.put(url, files={"photo": ("a.txt", b"text", "text/plain")})
    assert response.status_code == 422

    assert (await auth_client.delete(url)).json()["image_url"] is None
    assert (await auth_client.get(url)).status_code == 404


async def test_exercises_are_isolated_between_users(auth_client: AsyncClient) -> None:
    exercise = (await auth_client.post("/gym/exercises", json=exercise_payload("Squat"))).json()
    other = await register_and_login(auth_client, "other@example.com")

    response = await auth_client.get(f"/gym/exercises/{exercise['id']}", headers=other)
    assert response.status_code == 404
    assert (await auth_client.get("/gym/exercises", headers=other)).json() == []


async def test_exercises_require_auth(client: AsyncClient) -> None:
    assert (await client.get("/gym/exercises")).status_code == 401


async def test_create_defaults_secondary_muscles_to_empty(auth_client: AsyncClient) -> None:
    response = await auth_client.post("/gym/exercises", json=exercise_payload("Squat"))
    assert response.status_code == 201
    assert response.json()["secondary_muscles"] == []
    assert response.json()["instructions"] is None


@pytest.mark.parametrize("field", ["muscle_group", "equipment", "exercise_type"])
async def test_create_requires_classification_fields(auth_client: AsyncClient, field: str) -> None:
    payload = exercise_payload("Squat")
    del payload[field]
    assert (await auth_client.post("/gym/exercises", json=payload)).status_code == 422


async def test_create_rejects_unknown_enum_values(auth_client: AsyncClient) -> None:
    payload = exercise_payload("Squat", secondary_muscles=["wings"])
    assert (await auth_client.post("/gym/exercises", json=payload)).status_code == 422


async def test_create_rejects_primary_muscle_among_secondary(auth_client: AsyncClient) -> None:
    payload = exercise_payload("Squat", secondary_muscles=["glutes", "quadriceps"])
    response = await auth_client.post("/gym/exercises", json=payload)
    assert response.status_code == 422


@pytest.mark.parametrize(
    "field", ["name", "muscle_group", "secondary_muscles", "equipment", "exercise_type"]
)
async def test_update_rejects_null_for_required_fields(
    auth_client: AsyncClient, field: str
) -> None:
    exercise = (await auth_client.post("/gym/exercises", json=exercise_payload("Squat"))).json()
    response = await auth_client.patch(f"/gym/exercises/{exercise['id']}", json={field: None})
    assert response.status_code == 422


async def test_update_allows_clearing_instructions(auth_client: AsyncClient) -> None:
    payload = exercise_payload("Squat", instructions="Brace")
    exercise = (await auth_client.post("/gym/exercises", json=payload)).json()
    response = await auth_client.patch(
        f"/gym/exercises/{exercise['id']}", json={"instructions": None}
    )
    assert response.status_code == 200
    assert response.json()["instructions"] is None
