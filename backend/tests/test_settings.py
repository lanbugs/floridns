import pytest
from httpx import AsyncClient

from app.models.user import User
from tests.conftest import bearer, get_token


async def test_get_settings_as_superadmin(client: AsyncClient, superadmin: User) -> None:
    token = await get_token(client, "superadmin")
    r = await client.get("/api/v1/settings", headers=bearer(token))
    assert r.status_code == 200
    assert isinstance(r.json(), dict)


async def test_get_settings_forbidden_for_admin(client: AsyncClient, admin: User) -> None:
    token = await get_token(client, "admin")
    r = await client.get("/api/v1/settings", headers=bearer(token))
    assert r.status_code == 403


async def test_get_settings_forbidden_for_viewer(client: AsyncClient, viewer: User) -> None:
    token = await get_token(client, "viewer")
    r = await client.get("/api/v1/settings", headers=bearer(token))
    assert r.status_code == 403


async def test_get_settings_requires_auth(client: AsyncClient) -> None:
    r = await client.get("/api/v1/settings")
    assert r.status_code == 401


async def test_put_setting_as_superadmin(client: AsyncClient, superadmin: User) -> None:
    token = await get_token(client, "superadmin")
    r = await client.put("/api/v1/settings/zone_history_enabled", headers=bearer(token),
                         json={"value": True})
    assert r.status_code == 200
    assert r.json()["zone_history_enabled"] is True


async def test_put_setting_forbidden_for_admin(client: AsyncClient, admin: User) -> None:
    token = await get_token(client, "admin")
    r = await client.put("/api/v1/settings/zone_history_enabled", headers=bearer(token),
                         json={"value": True})
    assert r.status_code == 403


async def test_put_setting_forbidden_for_viewer(client: AsyncClient, viewer: User) -> None:
    token = await get_token(client, "viewer")
    r = await client.put("/api/v1/settings/zone_history_enabled", headers=bearer(token),
                         json={"value": True})
    assert r.status_code == 403


async def test_put_invalid_key(client: AsyncClient, superadmin: User) -> None:
    token = await get_token(client, "superadmin")
    r = await client.put("/api/v1/settings/nonexistent_key", headers=bearer(token),
                         json={"value": "x"})
    assert r.status_code == 422


async def test_put_setting_updates_value(client: AsyncClient, superadmin: User) -> None:
    token = await get_token(client, "superadmin")
    await client.put("/api/v1/settings/require_totp", headers=bearer(token), json={"value": True})
    await client.put("/api/v1/settings/require_totp", headers=bearer(token), json={"value": False})
    r = await client.get("/api/v1/settings", headers=bearer(token))
    assert r.json()["require_totp"] is False


async def test_put_allowed_record_types_operator(client: AsyncClient, superadmin: User) -> None:
    token = await get_token(client, "superadmin")
    r = await client.put("/api/v1/settings/allowed_record_types_operator", headers=bearer(token),
                         json={"value": ["A", "AAAA", "CNAME"]})
    assert r.status_code == 200


async def test_put_ldap_config(client: AsyncClient, superadmin: User) -> None:
    token = await get_token(client, "superadmin")
    cfg = {
        "enabled": False, "url": "ldap://ldap.example.com", "bind_dn": "cn=admin,dc=example,dc=com",
        "bind_password": "secret", "base_dn": "ou=users,dc=example,dc=com",
        "user_attr": "uid", "email_attr": "mail", "tls": "none",
        "group_attr": "memberOf", "group_mapping": [],
    }
    r = await client.put("/api/v1/settings/ldap_config", headers=bearer(token), json={"value": cfg})
    assert r.status_code == 200


async def test_put_oidc_config(client: AsyncClient, superadmin: User) -> None:
    token = await get_token(client, "superadmin")
    cfg = {
        "enabled": False, "issuer_url": "https://accounts.example.com",
        "client_id": "floridns", "client_secret": "secret",
        "redirect_uri": "https://floridns.example.com/auth/callback",
        "scopes": "openid email profile", "role_claim": "roles", "role_mapping": [],
    }
    r = await client.put("/api/v1/settings/oidc_config", headers=bearer(token), json={"value": cfg})
    assert r.status_code == 200
