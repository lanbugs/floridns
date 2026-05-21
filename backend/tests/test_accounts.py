import pytest
from httpx import AsyncClient

from app.models.user import User
from tests.conftest import bearer, get_token


async def test_list_accounts_as_admin(client: AsyncClient, admin: User) -> None:
    token = await get_token(client, "admin")
    r = await client.get("/api/v1/accounts", headers=bearer(token))
    assert r.status_code == 200
    assert isinstance(r.json(), list)


async def test_list_accounts_for_viewer_returns_own_accounts(client: AsyncClient, viewer: User) -> None:
    # Viewers get a filtered list (only accounts they belong to), not 403
    token = await get_token(client, "viewer")
    r = await client.get("/api/v1/accounts", headers=bearer(token))
    assert r.status_code == 200
    assert r.json() == []  # viewer has no account memberships yet


async def test_create_account(client: AsyncClient, admin: User) -> None:
    token = await get_token(client, "admin")
    r = await client.post("/api/v1/accounts", headers=bearer(token),
                          json={"name": "TestCorp", "description": "Test account"})
    assert r.status_code == 201
    assert r.json()["name"] == "TestCorp"


async def test_create_account_duplicate_name(client: AsyncClient, admin: User) -> None:
    token = await get_token(client, "admin")
    await client.post("/api/v1/accounts", headers=bearer(token), json={"name": "dup"})
    r = await client.post("/api/v1/accounts", headers=bearer(token), json={"name": "dup"})
    assert r.status_code == 409


async def test_get_account(client: AsyncClient, admin: User) -> None:
    token = await get_token(client, "admin")
    created = await client.post("/api/v1/accounts", headers=bearer(token),
                                json={"name": "Corp"})
    acc_id = created.json()["id"]
    r = await client.get(f"/api/v1/accounts/{acc_id}", headers=bearer(token))
    assert r.status_code == 200
    assert r.json()["name"] == "Corp"


async def test_get_account_not_found(client: AsyncClient, admin: User) -> None:
    import uuid
    token = await get_token(client, "admin")
    r = await client.get(f"/api/v1/accounts/{uuid.uuid4()}", headers=bearer(token))
    assert r.status_code == 404


async def test_update_account(client: AsyncClient, admin: User) -> None:
    token = await get_token(client, "admin")
    created = await client.post("/api/v1/accounts", headers=bearer(token), json={"name": "Old"})
    acc_id = created.json()["id"]
    r = await client.patch(f"/api/v1/accounts/{acc_id}", headers=bearer(token),
                           json={"name": "New", "description": "updated"})
    assert r.status_code == 200
    assert r.json()["name"] == "New"


async def test_delete_account(client: AsyncClient, admin: User) -> None:
    token = await get_token(client, "admin")
    created = await client.post("/api/v1/accounts", headers=bearer(token), json={"name": "ToDelete"})
    acc_id = created.json()["id"]
    r = await client.delete(f"/api/v1/accounts/{acc_id}", headers=bearer(token))
    assert r.status_code == 204


async def test_add_zone_to_account(client: AsyncClient, admin: User) -> None:
    token = await get_token(client, "admin")
    created = await client.post("/api/v1/accounts", headers=bearer(token), json={"name": "Corp"})
    acc_id = created.json()["id"]
    r = await client.post(f"/api/v1/accounts/{acc_id}/zones", headers=bearer(token),
                          json={"zone_name": "example.com."})
    assert r.status_code in (200, 201)


async def test_remove_zone_from_account(client: AsyncClient, admin: User) -> None:
    token = await get_token(client, "admin")
    created = await client.post("/api/v1/accounts", headers=bearer(token), json={"name": "Corp"})
    acc_id = created.json()["id"]
    await client.post(f"/api/v1/accounts/{acc_id}/zones", headers=bearer(token),
                      json={"zone_name": "example.com."})
    r = await client.delete(f"/api/v1/accounts/{acc_id}/zones",
                            headers=bearer(token), params={"zone_name": "example.com."})
    assert r.status_code == 204


async def test_add_user_to_account(client: AsyncClient, admin: User, viewer: User) -> None:
    token = await get_token(client, "admin")
    created = await client.post("/api/v1/accounts", headers=bearer(token), json={"name": "Corp"})
    acc_id = created.json()["id"]
    r = await client.post(f"/api/v1/accounts/{acc_id}/users", headers=bearer(token),
                          json={"user_id": str(viewer.id), "role": "viewer"})
    assert r.status_code in (200, 201)


async def test_remove_user_from_account(client: AsyncClient, admin: User, viewer: User) -> None:
    token = await get_token(client, "admin")
    created = await client.post("/api/v1/accounts", headers=bearer(token), json={"name": "Corp"})
    acc_id = created.json()["id"]
    await client.post(f"/api/v1/accounts/{acc_id}/users", headers=bearer(token),
                      json={"user_id": str(viewer.id), "role": "viewer"})
    r = await client.delete(f"/api/v1/accounts/{acc_id}/users/{viewer.id}", headers=bearer(token))
    assert r.status_code == 204
