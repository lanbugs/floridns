import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.audit_service import log_action
from tests.conftest import bearer, get_token


async def _seed_logs(db: AsyncSession, user: User, count: int = 3) -> None:
    for i in range(count):
        await log_action(db, user=user, ip_address="127.0.0.1",
                         action=f"action.{i}", resource_type="zone",
                         resource_id="example.com.")
    await db.commit()


async def test_list_audit_as_admin(client: AsyncClient, db: AsyncSession, admin: User) -> None:
    await _seed_logs(db, admin, 3)
    token = await get_token(client, "admin")
    r = await client.get("/api/v1/audit", headers=bearer(token))
    assert r.status_code == 200
    assert r.json()["total"] == 3


async def test_audit_requires_admin(client: AsyncClient, viewer: User) -> None:
    token = await get_token(client, "viewer")
    r = await client.get("/api/v1/audit", headers=bearer(token))
    assert r.status_code == 403


async def test_audit_requires_admin_operator(client: AsyncClient, operator: User) -> None:
    token = await get_token(client, "operator")
    r = await client.get("/api/v1/audit", headers=bearer(token))
    assert r.status_code == 403


async def test_audit_pagination(client: AsyncClient, db: AsyncSession, admin: User) -> None:
    await _seed_logs(db, admin, 5)
    token = await get_token(client, "admin")
    r = await client.get("/api/v1/audit?page=1&page_size=2", headers=bearer(token))
    assert r.status_code == 200
    data = r.json()
    assert len(data["items"]) == 2
    assert data["total"] == 5


async def test_audit_filter_by_action(client: AsyncClient, db: AsyncSession, admin: User) -> None:
    await _seed_logs(db, admin, 3)
    token = await get_token(client, "admin")
    r = await client.get("/api/v1/audit?action=action.0", headers=bearer(token))
    assert r.json()["total"] == 1


async def test_audit_filter_by_resource(client: AsyncClient, db: AsyncSession, admin: User) -> None:
    await _seed_logs(db, admin, 2)
    token = await get_token(client, "admin")
    r = await client.get("/api/v1/audit?resource_type=zone", headers=bearer(token))
    assert r.json()["total"] == 2


async def test_audit_requires_auth(client: AsyncClient) -> None:
    r = await client.get("/api/v1/audit")
    assert r.status_code == 401
