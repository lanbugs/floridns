from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole, ZonePermission
from tests.conftest import bearer, get_token


# ---------------------------------------------------------------------------
# List zones
# ---------------------------------------------------------------------------

async def test_list_zones_as_admin(client: AsyncClient, admin: User) -> None:
    token = await get_token(client, "admin")
    r = await client.get("/api/v1/zones", headers=bearer(token))
    assert r.status_code == 200
    assert r.json()["total"] >= 1


async def test_list_zones_requires_auth(client: AsyncClient) -> None:
    r = await client.get("/api/v1/zones")
    assert r.status_code == 401


async def test_list_zones_viewer_sees_only_permitted(
    client: AsyncClient, db: AsyncSession, viewer: User
) -> None:
    # No zone permission → empty list
    token = await get_token(client, "viewer")
    r = await client.get("/api/v1/zones", headers=bearer(token))
    assert r.status_code == 200
    assert r.json()["total"] == 0


async def test_list_zones_viewer_with_permission(
    client: AsyncClient, db: AsyncSession, viewer: User
) -> None:
    perm = ZonePermission(user_id=viewer.id, zone_name="example.com.", role=UserRole.viewer)
    db.add(perm)
    await db.commit()
    token = await get_token(client, "viewer")
    r = await client.get("/api/v1/zones", headers=bearer(token))
    assert r.json()["total"] == 1


async def test_list_zones_search_filter(client: AsyncClient, admin: User, pdns_mock: MagicMock) -> None:
    token = await get_token(client, "admin")
    r = await client.get("/api/v1/zones?search=example", headers=bearer(token))
    assert r.status_code == 200
    assert r.json()["total"] == 1


async def test_list_zones_kind_filter(client: AsyncClient, admin: User) -> None:
    token = await get_token(client, "admin")
    r = await client.get("/api/v1/zones?kind=Slave", headers=bearer(token))
    assert r.json()["total"] == 0


async def test_list_zones_pagination(client: AsyncClient, admin: User) -> None:
    token = await get_token(client, "admin")
    r = await client.get("/api/v1/zones?page=1&page_size=10", headers=bearer(token))
    assert r.status_code == 200
    assert "items" in r.json()


# ---------------------------------------------------------------------------
# Get zone
# ---------------------------------------------------------------------------

async def test_get_zone_as_admin(client: AsyncClient, admin: User) -> None:
    token = await get_token(client, "admin")
    r = await client.get("/api/v1/zones/example.com.", headers=bearer(token))
    assert r.status_code == 200
    assert r.json()["name"] == "example.com."


async def test_get_zone_not_found(client: AsyncClient, admin: User, pdns_mock: MagicMock) -> None:
    from app.services.pdns_client import PdnsError
    pdns_mock.get_zone = AsyncMock(side_effect=PdnsError("Not found", 404))
    token = await get_token(client, "admin")
    r = await client.get("/api/v1/zones/nonexistent.com.", headers=bearer(token))
    assert r.status_code == 404


async def test_get_zone_forbidden_for_viewer_without_permission(
    client: AsyncClient, viewer: User
) -> None:
    token = await get_token(client, "viewer")
    r = await client.get("/api/v1/zones/example.com.", headers=bearer(token))
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Create zone
# ---------------------------------------------------------------------------

async def test_create_zone_as_admin(client: AsyncClient, admin: User) -> None:
    token = await get_token(client, "admin")
    r = await client.post("/api/v1/zones", headers=bearer(token), json={
        "name": "newzone.com.", "kind": "Master", "nameservers": ["ns1.newzone.com."],
    })
    assert r.status_code == 201


async def test_create_zone_forbidden_for_viewer(client: AsyncClient, viewer: User) -> None:
    token = await get_token(client, "viewer")
    r = await client.post("/api/v1/zones", headers=bearer(token), json={
        "name": "x.com.", "kind": "Master",
    })
    assert r.status_code == 403


async def test_create_zone_invalid_kind(client: AsyncClient, admin: User) -> None:
    token = await get_token(client, "admin")
    r = await client.post("/api/v1/zones", headers=bearer(token), json={
        "name": "x.com.", "kind": "InvalidKind",
    })
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Update zone
# ---------------------------------------------------------------------------

async def test_update_zone_kind(client: AsyncClient, admin: User) -> None:
    token = await get_token(client, "admin")
    r = await client.put("/api/v1/zones/example.com.", headers=bearer(token),
                         json={"kind": "Native"})
    assert r.status_code == 200


async def test_update_zone_forbidden_for_viewer(client: AsyncClient, viewer: User) -> None:
    token = await get_token(client, "viewer")
    r = await client.put("/api/v1/zones/example.com.", headers=bearer(token),
                         json={"kind": "Native"})
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Delete zone
# ---------------------------------------------------------------------------

async def test_delete_zone_as_admin(client: AsyncClient, admin: User) -> None:
    token = await get_token(client, "admin")
    r = await client.delete("/api/v1/zones/example.com.", headers=bearer(token))
    assert r.status_code == 204


async def test_delete_zone_forbidden_for_operator(client: AsyncClient, operator: User) -> None:
    token = await get_token(client, "operator")
    r = await client.delete("/api/v1/zones/example.com.", headers=bearer(token))
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Export zone
# ---------------------------------------------------------------------------

async def test_export_zone(client: AsyncClient, admin: User) -> None:
    token = await get_token(client, "admin")
    r = await client.get("/api/v1/zones/example.com./export", headers=bearer(token))
    assert r.status_code == 200
    assert "example.com." in r.text


# ---------------------------------------------------------------------------
# DNSSEC
# ---------------------------------------------------------------------------

async def test_enable_dnssec(client: AsyncClient, admin: User) -> None:
    token = await get_token(client, "admin")
    r = await client.post("/api/v1/zones/example.com./dnssec/enable", headers=bearer(token))
    assert r.status_code == 204


async def test_disable_dnssec(client: AsyncClient, admin: User) -> None:
    token = await get_token(client, "admin")
    r = await client.post("/api/v1/zones/example.com./dnssec/disable", headers=bearer(token))
    assert r.status_code == 204


async def test_dnssec_forbidden_for_operator(client: AsyncClient, operator: User) -> None:
    token = await get_token(client, "operator")
    r = await client.post("/api/v1/zones/example.com./dnssec/enable", headers=bearer(token))
    assert r.status_code == 403
