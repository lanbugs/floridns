from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.setting import Setting
from app.models.user import User
from app.services.history_service import save_history
from tests.conftest import bearer, get_token

ZONE = "example.com."
BEFORE = [{"name": "host.example.com.", "type": "A", "ttl": 300,
            "records": [{"content": "1.2.3.4", "disabled": False}], "comments": []}]
AFTER = [{"name": "host.example.com.", "type": "A", "ttl": 300,
           "records": [{"content": "5.6.7.8", "disabled": False}], "comments": []}]


async def _enable_history(db: AsyncSession) -> None:
    import json
    db.add(Setting(key="zone_history_enabled", value=json.dumps(True), updated_by="test"))
    await db.commit()


async def _seed_history(db: AsyncSession, admin: User, count: int = 2) -> None:
    await _enable_history(db)
    for _ in range(count):
        await save_history(db, ZONE, "records.patch", admin.username, BEFORE, AFTER)
    await db.commit()


async def test_list_history_empty(client: AsyncClient, admin: User) -> None:
    token = await get_token(client, "admin")
    r = await client.get(f"/api/v1/zones/{ZONE}/history", headers=bearer(token))
    assert r.status_code == 200
    assert r.json()["total"] == 0


async def test_list_history(client: AsyncClient, db: AsyncSession, admin: User) -> None:
    await _seed_history(db, admin, 2)
    token = await get_token(client, "admin")
    r = await client.get(f"/api/v1/zones/{ZONE}/history", headers=bearer(token))
    assert r.status_code == 200
    assert r.json()["total"] == 2


async def test_list_history_forbidden_for_viewer(
    client: AsyncClient, db: AsyncSession, viewer: User, admin: User
) -> None:
    await _seed_history(db, admin, 1)
    token = await get_token(client, "viewer")
    r = await client.get(f"/api/v1/zones/{ZONE}/history", headers=bearer(token))
    assert r.status_code == 403


async def test_get_snapshot(client: AsyncClient, db: AsyncSession, admin: User) -> None:
    await _seed_history(db, admin, 1)
    token = await get_token(client, "admin")
    items = (await client.get(f"/api/v1/zones/{ZONE}/history", headers=bearer(token))).json()["items"]
    hist_id = items[0]["id"]
    r = await client.get(f"/api/v1/zones/{ZONE}/history/{hist_id}/snapshot", headers=bearer(token))
    assert r.status_code == 200
    data = r.json()
    assert "before" in data
    assert "after" in data


async def test_restore_history(
    client: AsyncClient, db: AsyncSession, admin: User, pdns_mock: MagicMock
) -> None:
    await _seed_history(db, admin, 1)
    token = await get_token(client, "admin")
    items = (await client.get(f"/api/v1/zones/{ZONE}/history", headers=bearer(token))).json()["items"]
    hist_id = items[0]["id"]
    r = await client.post(f"/api/v1/zones/{ZONE}/history/{hist_id}/restore",
                          headers=bearer(token), json={})
    assert r.status_code in (200, 204)


async def test_restore_history_forbidden_for_operator(
    client: AsyncClient, db: AsyncSession, operator: User, admin: User
) -> None:
    await _seed_history(db, admin, 1)
    token = await get_token(client, "admin")
    items = (await client.get(f"/api/v1/zones/{ZONE}/history", headers=bearer(token))).json()["items"]
    hist_id = items[0]["id"]
    op_token = await get_token(client, "operator")
    r = await client.post(f"/api/v1/zones/{ZONE}/history/{hist_id}/restore",
                          headers=bearer(op_token), json={})
    assert r.status_code == 403
