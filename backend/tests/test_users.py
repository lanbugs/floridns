import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole
from tests.conftest import bearer, get_token


# ---------------------------------------------------------------------------
# List users
# ---------------------------------------------------------------------------

async def test_list_users_as_admin(client: AsyncClient, admin: User) -> None:
    token = await get_token(client, "admin")
    r = await client.get("/api/v1/users", headers=bearer(token))
    assert r.status_code == 200
    names = [u["username"] for u in r.json()]
    assert "admin" in names


async def test_list_users_forbidden_for_viewer(client: AsyncClient, viewer: User) -> None:
    token = await get_token(client, "viewer")
    r = await client.get("/api/v1/users", headers=bearer(token))
    assert r.status_code == 403


async def test_list_users_requires_auth(client: AsyncClient) -> None:
    r = await client.get("/api/v1/users")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Create user
# ---------------------------------------------------------------------------

async def test_create_user_as_admin(client: AsyncClient, admin: User) -> None:
    token = await get_token(client, "admin")
    r = await client.post("/api/v1/users", headers=bearer(token), json={
        "username": "newuser", "email": "new@example.com", "password": "pass1234", "role": "viewer",
    })
    assert r.status_code == 201
    assert r.json()["username"] == "newuser"


async def test_create_user_duplicate_username(client: AsyncClient, admin: User) -> None:
    token = await get_token(client, "admin")
    await client.post("/api/v1/users", headers=bearer(token), json={
        "username": "dup", "email": "dup1@example.com", "password": "pass1234",
    })
    r = await client.post("/api/v1/users", headers=bearer(token), json={
        "username": "dup", "email": "dup2@example.com", "password": "pass1234",
    })
    assert r.status_code == 409


async def test_admin_cannot_create_superadmin(client: AsyncClient, admin: User) -> None:
    token = await get_token(client, "admin")
    r = await client.post("/api/v1/users", headers=bearer(token), json={
        "username": "newsuper", "email": "ns@example.com", "password": "pass1234", "role": "superadmin",
    })
    assert r.status_code == 403


async def test_superadmin_can_create_superadmin(client: AsyncClient, superadmin: User) -> None:
    token = await get_token(client, "superadmin")
    r = await client.post("/api/v1/users", headers=bearer(token), json={
        "username": "newsuper", "email": "ns@example.com", "password": "pass1234", "role": "superadmin",
    })
    assert r.status_code == 201


async def test_create_user_forbidden_for_operator(client: AsyncClient, operator: User) -> None:
    token = await get_token(client, "operator")
    r = await client.post("/api/v1/users", headers=bearer(token), json={
        "username": "newuser2", "email": "newuser2@example.com", "password": "pass1234",
    })
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Get / Update / Delete user
# ---------------------------------------------------------------------------

async def test_get_user_as_admin(client: AsyncClient, admin: User, viewer: User) -> None:
    token = await get_token(client, "admin")
    r = await client.get(f"/api/v1/users/{viewer.id}", headers=bearer(token))
    assert r.status_code == 200
    assert r.json()["username"] == "viewer"


async def test_get_own_user(client: AsyncClient, viewer: User) -> None:
    token = await get_token(client, "viewer")
    r = await client.get(f"/api/v1/users/{viewer.id}", headers=bearer(token))
    assert r.status_code == 200


async def test_get_other_user_forbidden_for_viewer(client: AsyncClient, viewer: User, admin: User) -> None:
    token = await get_token(client, "viewer")
    r = await client.get(f"/api/v1/users/{admin.id}", headers=bearer(token))
    assert r.status_code == 403


async def test_update_user_email(client: AsyncClient, admin: User, viewer: User) -> None:
    token = await get_token(client, "admin")
    r = await client.patch(f"/api/v1/users/{viewer.id}", headers=bearer(token),
                           json={"email": "updated@example.com"})
    assert r.status_code == 200
    assert r.json()["email"] == "updated@example.com"


async def test_delete_user_as_superadmin(client: AsyncClient, superadmin: User, viewer: User) -> None:
    token = await get_token(client, "superadmin")
    r = await client.delete(f"/api/v1/users/{viewer.id}", headers=bearer(token))
    assert r.status_code == 204


async def test_delete_user_forbidden_for_admin(client: AsyncClient, admin: User, viewer: User) -> None:
    token = await get_token(client, "admin")
    r = await client.delete(f"/api/v1/users/{viewer.id}", headers=bearer(token))
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# API keys
# ---------------------------------------------------------------------------

async def test_create_api_key(client: AsyncClient, viewer: User) -> None:
    token = await get_token(client, "viewer")
    r = await client.post(f"/api/v1/users/{viewer.id}/api-keys", headers=bearer(token),
                          json={"name": "mykey", "scope": "read-only"})
    assert r.status_code == 201
    data = r.json()
    assert data["scope"] == "read-only"
    assert "key" in data


async def test_create_acme_key_with_zone_restriction(client: AsyncClient, viewer: User) -> None:
    token = await get_token(client, "viewer")
    r = await client.post(f"/api/v1/users/{viewer.id}/api-keys", headers=bearer(token),
                          json={"name": "acmekey", "scope": "acme", "zone_restriction": "example.com."})
    assert r.status_code == 201
    assert r.json()["zone_restriction"] == "example.com."


async def test_create_key_invalid_scope(client: AsyncClient, viewer: User) -> None:
    token = await get_token(client, "viewer")
    r = await client.post(f"/api/v1/users/{viewer.id}/api-keys", headers=bearer(token),
                          json={"name": "k", "scope": "superpower"})
    assert r.status_code == 422


async def test_list_api_keys(client: AsyncClient, viewer: User) -> None:
    token = await get_token(client, "viewer")
    await client.post(f"/api/v1/users/{viewer.id}/api-keys", headers=bearer(token),
                      json={"name": "k1", "scope": "read-only"})
    r = await client.get(f"/api/v1/users/{viewer.id}/api-keys", headers=bearer(token))
    assert r.status_code == 200
    assert len(r.json()) == 1


async def test_delete_api_key(client: AsyncClient, viewer: User) -> None:
    token = await get_token(client, "viewer")
    created = await client.post(f"/api/v1/users/{viewer.id}/api-keys", headers=bearer(token),
                                json={"name": "k", "scope": "read-only"})
    key_id = created.json()["id"]
    r = await client.delete(f"/api/v1/users/{viewer.id}/api-keys/{key_id}", headers=bearer(token))
    assert r.status_code == 204


async def test_api_key_forbidden_for_other_user(client: AsyncClient, viewer: User, admin: User) -> None:
    token = await get_token(client, "viewer")
    r = await client.get(f"/api/v1/users/{admin.id}/api-keys", headers=bearer(token))
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Zone permissions
# ---------------------------------------------------------------------------

async def test_add_zone_permission(client: AsyncClient, admin: User, viewer: User) -> None:
    token = await get_token(client, "admin")
    r = await client.post(f"/api/v1/users/{viewer.id}/zone-permissions", headers=bearer(token),
                          json={"zone_name": "example.com.", "role": "operator"})
    assert r.status_code == 201
    assert r.json()["zone_name"] == "example.com."


async def test_list_zone_permissions(client: AsyncClient, admin: User, viewer: User) -> None:
    token = await get_token(client, "admin")
    await client.post(f"/api/v1/users/{viewer.id}/zone-permissions", headers=bearer(token),
                      json={"zone_name": "example.com.", "role": "operator"})
    r = await client.get(f"/api/v1/users/{viewer.id}/zone-permissions", headers=bearer(token))
    assert r.status_code == 200
    assert len(r.json()) == 1


async def test_delete_zone_permission(client: AsyncClient, admin: User, viewer: User) -> None:
    token = await get_token(client, "admin")
    created = await client.post(f"/api/v1/users/{viewer.id}/zone-permissions", headers=bearer(token),
                                json={"zone_name": "example.com.", "role": "operator"})
    perm_id = created.json()["id"]
    r = await client.delete(f"/api/v1/users/{viewer.id}/zone-permissions/{perm_id}", headers=bearer(token))
    assert r.status_code == 204
