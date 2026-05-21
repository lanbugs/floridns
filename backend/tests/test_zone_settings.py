import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole, ZonePermission
from tests.conftest import bearer, get_token

ZONE = "example.com."
URL = f"/api/v1/zones/{ZONE}/settings"


async def _grant(db: AsyncSession, user: User, role: UserRole) -> None:
    db.add(ZonePermission(user_id=user.id, zone_name=ZONE, role=role))
    await db.commit()


async def test_get_zone_settings_defaults_to_false(client: AsyncClient, admin: User) -> None:
    token = await get_token(client, "admin")
    r = await client.get(URL, headers=bearer(token))
    assert r.status_code == 200
    assert r.json()["auto_ptr"] is False


async def test_get_zone_settings_forbidden_for_operator(
    client: AsyncClient, db: AsyncSession, operator: User
) -> None:
    await _grant(db, operator, UserRole.operator)
    token = await get_token(client, "operator")
    r = await client.get(URL, headers=bearer(token))
    assert r.status_code == 403


async def test_put_zone_settings_as_admin(client: AsyncClient, admin: User) -> None:
    token = await get_token(client, "admin")
    r = await client.put(URL, headers=bearer(token), json={"auto_ptr": True})
    assert r.status_code == 200
    assert r.json()["auto_ptr"] is True


async def test_put_zone_settings_persists(client: AsyncClient, admin: User) -> None:
    token = await get_token(client, "admin")
    await client.put(URL, headers=bearer(token), json={"auto_ptr": True})
    r = await client.get(URL, headers=bearer(token))
    assert r.json()["auto_ptr"] is True


async def test_put_zone_settings_toggle(client: AsyncClient, admin: User) -> None:
    token = await get_token(client, "admin")
    await client.put(URL, headers=bearer(token), json={"auto_ptr": True})
    await client.put(URL, headers=bearer(token), json={"auto_ptr": False})
    r = await client.get(URL, headers=bearer(token))
    assert r.json()["auto_ptr"] is False


async def test_put_zone_settings_forbidden_for_operator(
    client: AsyncClient, db: AsyncSession, operator: User
) -> None:
    await _grant(db, operator, UserRole.operator)
    token = await get_token(client, "operator")
    r = await client.put(URL, headers=bearer(token), json={"auto_ptr": True})
    assert r.status_code == 403


async def test_put_zone_settings_requires_auth(client: AsyncClient) -> None:
    r = await client.put(URL, json={"auto_ptr": True})
    assert r.status_code == 401
