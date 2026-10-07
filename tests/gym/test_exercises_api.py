from httpx import AsyncClient

from tests.conftest import register_and_login


async def test_exercise_crud(auth_client: AsyncClient) -> None:
    response = await auth_client.post(
        "/gym/exercises", json={"name": "Stair climber", "category": "cardio"}
    )
    assert response.status_code == 201
    exercise = response.json()
    assert exercise["photo_url"] is None

    response = await auth_client.patch(
        f"/gym/exercises/{exercise['id']}", json={"notes": "Level 5-10"}
    )
    assert response.json()["notes"] == "Level 5-10"

    response = await auth_client.get("/gym/exercises")
    assert [e["name"] for e in response.json()] == ["Stair climber"]

    response = await auth_client.delete(f"/gym/exercises/{exercise['id']}")
    assert response.status_code == 204
    assert (await auth_client.get(f"/gym/exercises/{exercise['id']}")).status_code == 404


async def test_duplicate_exercise_name_conflicts(auth_client: AsyncClient) -> None:
    assert (await auth_client.post("/gym/exercises", json={"name": "Squat"})).status_code == 201
    assert (await auth_client.post("/gym/exercises", json={"name": "squat"})).status_code == 409


async def test_photo_upload_download_and_delete(auth_client: AsyncClient) -> None:
    exercise = (await auth_client.post("/gym/exercises", json={"name": "Squat"})).json()
    url = f"/gym/exercises/{exercise['id']}/photo"

    response = await auth_client.put(url, files={"photo": ("p.png", b"\x89PNG-data", "image/png")})
    assert response.status_code == 200
    assert response.json()["photo_url"] == url

    response = await auth_client.get(url)
    assert response.status_code == 200
    assert response.content == b"\x89PNG-data"
    assert response.headers["content-type"] == "image/png"

    response = await auth_client.put(url, files={"photo": ("a.txt", b"text", "text/plain")})
    assert response.status_code == 422

    assert (await auth_client.delete(url)).json()["photo_url"] is None
    assert (await auth_client.get(url)).status_code == 404


async def test_exercises_are_isolated_between_users(auth_client: AsyncClient) -> None:
    exercise = (await auth_client.post("/gym/exercises", json={"name": "Squat"})).json()
    other = await register_and_login(auth_client, "other@example.com")

    response = await auth_client.get(f"/gym/exercises/{exercise['id']}", headers=other)
    assert response.status_code == 404
    assert (await auth_client.get("/gym/exercises", headers=other)).json() == []


async def test_exercises_require_auth(client: AsyncClient) -> None:
    assert (await client.get("/gym/exercises")).status_code == 401
