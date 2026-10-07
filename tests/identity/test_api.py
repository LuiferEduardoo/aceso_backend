from httpx import AsyncClient


async def test_register_login_and_me(client: AsyncClient) -> None:
    response = await client.post(
        "/auth/register", json={"email": "Me@Example.com", "password": "password123"}
    )
    assert response.status_code == 201
    assert response.json()["email"] == "me@example.com"
    assert "password_hash" not in response.json()

    response = await client.post(
        "/auth/login", data={"username": "me@example.com", "password": "password123"}
    )
    assert response.status_code == 200
    token = response.json()["access_token"]

    response = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["email"] == "me@example.com"


async def test_register_duplicate_email_conflicts(client: AsyncClient) -> None:
    payload = {"email": "dup@example.com", "password": "password123"}
    assert (await client.post("/auth/register", json=payload)).status_code == 201
    payload["email"] = "DUP@example.com"
    assert (await client.post("/auth/register", json=payload)).status_code == 409


async def test_login_with_wrong_password_is_unauthorized(client: AsyncClient) -> None:
    await client.post("/auth/register", json={"email": "a@example.com", "password": "password123"})
    response = await client.post(
        "/auth/login", data={"username": "a@example.com", "password": "wrong-password"}
    )
    assert response.status_code == 401


async def test_me_requires_valid_token(client: AsyncClient) -> None:
    assert (await client.get("/auth/me")).status_code == 401
    response = await client.get("/auth/me", headers={"Authorization": "Bearer garbage"})
    assert response.status_code == 401
