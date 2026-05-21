import pytest
from httpx import AsyncClient

from app.models.user import User
from tests.conftest import bearer, get_token

TEMPLATE_BODY = {
    "name": "Basic Web",
    "description": "A, CNAME, MX",
    "records": [
        {"name": "@", "type": "A", "ttl": 3600, "content": "1.2.3.4"},
        {"name": "www", "type": "CNAME", "ttl": 3600, "content": "@"},
        {"name": "@", "type": "MX", "ttl": 3600, "content": "10 mail"},
    ],
}


async def test_list_templates_as_admin(client: AsyncClient, admin: User) -> None:
    token = await get_token(client, "admin")
    r = await client.get("/api/v1/templates", headers=bearer(token))
    assert r.status_code == 200
    assert isinstance(r.json(), list)


async def test_list_templates_requires_auth(client: AsyncClient) -> None:
    r = await client.get("/api/v1/templates")
    assert r.status_code == 401


async def test_create_template_as_admin(client: AsyncClient, admin: User) -> None:
    token = await get_token(client, "admin")
    r = await client.post("/api/v1/templates", headers=bearer(token), json=TEMPLATE_BODY)
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "Basic Web"
    assert len(data["records"]) == 3


async def test_create_template_forbidden_for_viewer(client: AsyncClient, viewer: User) -> None:
    token = await get_token(client, "viewer")
    r = await client.post("/api/v1/templates", headers=bearer(token), json=TEMPLATE_BODY)
    assert r.status_code == 403


async def test_get_template(client: AsyncClient, admin: User) -> None:
    token = await get_token(client, "admin")
    created = await client.post("/api/v1/templates", headers=bearer(token), json=TEMPLATE_BODY)
    tpl_id = created.json()["id"]
    r = await client.get(f"/api/v1/templates/{tpl_id}", headers=bearer(token))
    assert r.status_code == 200
    assert r.json()["name"] == "Basic Web"


async def test_get_template_not_found(client: AsyncClient, admin: User) -> None:
    import uuid
    token = await get_token(client, "admin")
    r = await client.get(f"/api/v1/templates/{uuid.uuid4()}", headers=bearer(token))
    assert r.status_code == 404


async def test_update_template(client: AsyncClient, admin: User) -> None:
    token = await get_token(client, "admin")
    created = await client.post("/api/v1/templates", headers=bearer(token), json=TEMPLATE_BODY)
    tpl_id = created.json()["id"]
    r = await client.put(f"/api/v1/templates/{tpl_id}", headers=bearer(token),
                         json={**TEMPLATE_BODY, "name": "Updated"})
    assert r.status_code == 200
    assert r.json()["name"] == "Updated"


async def test_delete_template(client: AsyncClient, admin: User) -> None:
    token = await get_token(client, "admin")
    created = await client.post("/api/v1/templates", headers=bearer(token), json=TEMPLATE_BODY)
    tpl_id = created.json()["id"]
    r = await client.delete(f"/api/v1/templates/{tpl_id}", headers=bearer(token))
    assert r.status_code == 204


async def test_apply_template(client: AsyncClient, admin: User) -> None:
    token = await get_token(client, "admin")
    created = await client.post("/api/v1/templates", headers=bearer(token), json=TEMPLATE_BODY)
    tpl_id = created.json()["id"]
    r = await client.post(f"/api/v1/templates/{tpl_id}/apply/example.com.",
                          headers=bearer(token), json={})
    assert r.status_code in (200, 204)


async def test_apply_template_not_found(client: AsyncClient, admin: User) -> None:
    import uuid
    token = await get_token(client, "admin")
    r = await client.post(f"/api/v1/templates/{uuid.uuid4()}/apply/example.com.",
                          headers=bearer(token), json={})
    assert r.status_code == 404
