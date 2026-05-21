"""Tests for DynDNS 2 host management CRUD and /nic/update protocol endpoint."""
from base64 import b64encode

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from tests.conftest import bearer, get_token

HOST_BODY = {
    "hostname": "home",
    "zone_name": "example.com",
    "description": "Home router",
}


def basic_auth(username: str, password: str) -> dict[str, str]:
    token = b64encode(f"{username}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

async def test_create_dyndns_host(client: AsyncClient, admin: User) -> None:
    token = await get_token(client, "admin")
    r = await client.post("/api/v1/dyndns/hosts", headers=bearer(token), json=HOST_BODY)
    assert r.status_code == 201
    data = r.json()
    assert data["hostname"] == "home.example.com."
    assert data["zone_name"] == "example.com."
    assert "token" in data
    assert data["token"]


async def test_create_dyndns_host_duplicate(client: AsyncClient, admin: User) -> None:
    token = await get_token(client, "admin")
    await client.post("/api/v1/dyndns/hosts", headers=bearer(token), json=HOST_BODY)
    r = await client.post("/api/v1/dyndns/hosts", headers=bearer(token), json=HOST_BODY)
    assert r.status_code == 409


async def test_list_dyndns_hosts(client: AsyncClient, admin: User) -> None:
    token = await get_token(client, "admin")
    await client.post("/api/v1/dyndns/hosts", headers=bearer(token), json=HOST_BODY)
    r = await client.get("/api/v1/dyndns/hosts", headers=bearer(token))
    assert r.status_code == 200
    assert len(r.json()) == 1


async def test_list_dyndns_hosts_isolated_per_user(client: AsyncClient, admin: User, viewer: User) -> None:
    admin_token = await get_token(client, "admin")
    viewer_token = await get_token(client, "viewer")
    await client.post("/api/v1/dyndns/hosts", headers=bearer(admin_token), json=HOST_BODY)
    r = await client.get("/api/v1/dyndns/hosts", headers=bearer(viewer_token))
    assert r.status_code == 200
    assert r.json() == []


async def test_update_dyndns_host(client: AsyncClient, admin: User) -> None:
    token = await get_token(client, "admin")
    created = (await client.post("/api/v1/dyndns/hosts", headers=bearer(token), json=HOST_BODY)).json()
    r = await client.patch(f"/api/v1/dyndns/hosts/{created['id']}", headers=bearer(token),
                           json={"description": "Updated", "is_active": False})
    assert r.status_code == 200
    assert r.json()["description"] == "Updated"
    assert r.json()["is_active"] is False


async def test_delete_dyndns_host(client: AsyncClient, admin: User) -> None:
    token = await get_token(client, "admin")
    created = (await client.post("/api/v1/dyndns/hosts", headers=bearer(token), json=HOST_BODY)).json()
    r = await client.delete(f"/api/v1/dyndns/hosts/{created['id']}", headers=bearer(token))
    assert r.status_code == 204


async def test_regenerate_token(client: AsyncClient, admin: User) -> None:
    token = await get_token(client, "admin")
    created = (await client.post("/api/v1/dyndns/hosts", headers=bearer(token), json=HOST_BODY)).json()
    old_token = created["token"]
    r = await client.post(f"/api/v1/dyndns/hosts/{created['id']}/regenerate-token",
                          headers=bearer(token), json={})
    assert r.status_code == 200
    assert r.json()["token"] != old_token


async def test_cannot_access_other_users_host(client: AsyncClient, admin: User, viewer: User) -> None:
    admin_token = await get_token(client, "admin")
    viewer_token = await get_token(client, "viewer")
    created = (await client.post("/api/v1/dyndns/hosts", headers=bearer(admin_token), json=HOST_BODY)).json()
    r = await client.delete(f"/api/v1/dyndns/hosts/{created['id']}", headers=bearer(viewer_token))
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# /nic/update protocol
# ---------------------------------------------------------------------------

async def _create_host(client: AsyncClient, token: str) -> dict:
    return (await client.post("/api/v1/dyndns/hosts", headers=bearer(token), json=HOST_BODY)).json()


async def test_nic_update_good(client: AsyncClient, admin: User) -> None:
    token = await get_token(client, "admin")
    host = await _create_host(client, token)
    hostname = host["hostname"]
    r = await client.get(
        "/nic/update",
        params={"hostname": hostname, "myip": "1.2.3.4"},
        headers=basic_auth(hostname, host["token"]),
    )
    assert r.status_code == 200
    assert r.text.startswith("good")
    assert "1.2.3.4" in r.text


async def test_nic_update_nochg(client: AsyncClient, admin: User) -> None:
    token = await get_token(client, "admin")
    host = await _create_host(client, token)
    hostname = host["hostname"]
    headers = basic_auth(hostname, host["token"])
    params = {"hostname": hostname, "myip": "1.2.3.4"}
    await client.get("/nic/update", params=params, headers=headers)
    r = await client.get("/nic/update", params=params, headers=headers)
    assert r.text.startswith("nochg")


async def test_nic_update_badauth_wrong_password(client: AsyncClient, admin: User) -> None:
    token = await get_token(client, "admin")
    host = await _create_host(client, token)
    hostname = host["hostname"]
    r = await client.get(
        "/nic/update",
        params={"hostname": hostname, "myip": "1.2.3.4"},
        headers=basic_auth(hostname, "wrongtoken"),
    )
    assert r.text == "badauth"


async def test_nic_update_no_auth(client: AsyncClient, admin: User) -> None:
    token = await get_token(client, "admin")
    host = await _create_host(client, token)
    r = await client.get("/nic/update", params={"hostname": host["hostname"], "myip": "1.2.3.4"})
    assert r.text == "badauth"


async def test_nic_update_nohost(client: AsyncClient, admin: User) -> None:
    r = await client.get(
        "/nic/update",
        params={"hostname": "unknown.example.com.", "myip": "1.2.3.4"},
        headers=basic_auth("unknown.example.com.", "sometoken"),
    )
    assert r.text == "nohost"


async def test_nic_update_inactive_host(client: AsyncClient, admin: User) -> None:
    token = await get_token(client, "admin")
    host = await _create_host(client, token)
    hostname = host["hostname"]
    host_id = host["id"]
    await client.patch(f"/api/v1/dyndns/hosts/{host_id}", headers=bearer(token), json={"is_active": False})
    r = await client.get(
        "/nic/update",
        params={"hostname": hostname, "myip": "1.2.3.4"},
        headers=basic_auth(hostname, host["token"]),
    )
    assert r.text == "abuse"


async def test_nic_update_invalid_ip(client: AsyncClient, admin: User) -> None:
    token = await get_token(client, "admin")
    host = await _create_host(client, token)
    hostname = host["hostname"]
    r = await client.get(
        "/nic/update",
        params={"hostname": hostname, "myip": "not-an-ip"},
        headers=basic_auth(hostname, host["token"]),
    )
    assert r.text == "dnserr"


async def test_nic_update_with_ipv6(client: AsyncClient, admin: User) -> None:
    token = await get_token(client, "admin")
    host = await _create_host(client, token)
    hostname = host["hostname"]
    r = await client.get(
        "/nic/update",
        params={"hostname": hostname, "myip": "1.2.3.4", "myip6": "2001:db8::1"},
        headers=basic_auth(hostname, host["token"]),
    )
    assert r.status_code == 200
    assert r.text.startswith("good")


async def test_nic_update_offline(client: AsyncClient, admin: User) -> None:
    token = await get_token(client, "admin")
    host = await _create_host(client, token)
    hostname = host["hostname"]
    # first set an IP
    await client.get("/nic/update", params={"hostname": hostname, "myip": "1.2.3.4"},
                     headers=basic_auth(hostname, host["token"]))
    # then go offline
    r = await client.get("/nic/update", params={"hostname": hostname, "offline": "yes"},
                         headers=basic_auth(hostname, host["token"]))
    assert r.status_code == 200
    assert r.text.startswith("good")
