import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import User, UserRole
from tests.conftest import bearer, get_token


@pytest.fixture
async def local_user(db: AsyncSession) -> User:
    user = User(
        username="localuser",
        email="local@example.com",
        hashed_password=hash_password("correctpass"),
        role=UserRole.viewer,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def inactive_user(db: AsyncSession) -> User:
    user = User(
        username="inactive",
        email="inactive@example.com",
        hashed_password=hash_password("pass1234"),
        role=UserRole.viewer,
        is_active=False,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

async def test_login_success(client: AsyncClient, local_user: User) -> None:
    r = await client.post("/api/v1/auth/login", json={"username": "localuser", "password": "correctpass"})
    assert r.status_code == 200
    data = r.json()
    assert data["token_type"] == "bearer"
    assert data["access_token"]
    # Refresh token is now delivered via httpOnly cookie, not response body
    assert "fdns_rt" in r.cookies


async def test_login_wrong_password(client: AsyncClient, local_user: User) -> None:
    r = await client.post("/api/v1/auth/login", json={"username": "localuser", "password": "wrong"})
    assert r.status_code == 401


async def test_login_unknown_user(client: AsyncClient) -> None:
    r = await client.post("/api/v1/auth/login", json={"username": "ghost", "password": "pass"})
    assert r.status_code == 401


async def test_login_inactive_user(client: AsyncClient, inactive_user: User) -> None:
    r = await client.post("/api/v1/auth/login", json={"username": "inactive", "password": "pass1234"})
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Account lockout
# ---------------------------------------------------------------------------

async def test_account_lockout_after_5_failures(client: AsyncClient, local_user: User, db: AsyncSession) -> None:
    for _ in range(4):
        r = await client.post("/api/v1/auth/login", json={"username": "localuser", "password": "wrong"})
        assert r.status_code == 401

    # 5th failure triggers lockout
    r = await client.post("/api/v1/auth/login", json={"username": "localuser", "password": "wrong"})
    assert r.status_code == 401

    # Subsequent attempt with correct password is rejected
    r = await client.post("/api/v1/auth/login", json={"username": "localuser", "password": "correctpass"})
    assert r.status_code == 429
    assert "locked" in r.json()["detail"].lower()


async def test_successful_login_resets_failure_counter(client: AsyncClient, local_user: User, db: AsyncSession) -> None:
    for _ in range(3):
        await client.post("/api/v1/auth/login", json={"username": "localuser", "password": "wrong"})

    # Successful login resets counter
    r = await client.post("/api/v1/auth/login", json={"username": "localuser", "password": "correctpass"})
    assert r.status_code == 200

    await db.refresh(local_user)
    assert local_user.failed_login_attempts == 0
    assert local_user.locked_until is None


# ---------------------------------------------------------------------------
# /me
# ---------------------------------------------------------------------------

async def test_me_requires_auth(client: AsyncClient) -> None:
    r = await client.get("/api/v1/auth/me")
    assert r.status_code == 401


async def test_me_returns_current_user(client: AsyncClient, local_user: User) -> None:
    token = await get_token(client, "localuser", "correctpass")
    r = await client.get("/api/v1/auth/me", headers=bearer(token))
    assert r.status_code == 200
    assert r.json()["username"] == "localuser"


# ---------------------------------------------------------------------------
# Token refresh (cookie-based)
# ---------------------------------------------------------------------------

async def test_refresh_returns_new_access_token(client: AsyncClient, local_user: User) -> None:
    login = await client.post("/api/v1/auth/login", json={"username": "localuser", "password": "correctpass"})
    rt_cookie = login.cookies.get("fdns_rt")
    assert rt_cookie, "Expected fdns_rt cookie after login"
    r = await client.post("/api/v1/auth/refresh", cookies={"fdns_rt": rt_cookie})
    assert r.status_code == 200
    assert r.json()["access_token"]


async def test_refresh_with_no_cookie_rejected(client: AsyncClient) -> None:
    r = await client.post("/api/v1/auth/refresh")
    assert r.status_code == 401


async def test_refresh_with_invalid_cookie_rejected(client: AsyncClient) -> None:
    r = await client.post("/api/v1/auth/refresh", cookies={"fdns_rt": "not-a-token"})
    assert r.status_code == 401


async def test_refresh_with_access_token_as_cookie_rejected(client: AsyncClient, local_user: User) -> None:
    login = await client.post("/api/v1/auth/login", json={"username": "localuser", "password": "correctpass"})
    access_token = login.json()["access_token"]
    r = await client.post("/api/v1/auth/refresh", cookies={"fdns_rt": access_token})
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Logout + token version invalidation
# ---------------------------------------------------------------------------

async def test_logout_invalidates_access_token(client: AsyncClient, local_user: User) -> None:
    token = await get_token(client, "localuser", "correctpass")
    # Logout
    r = await client.post("/api/v1/auth/logout", headers=bearer(token))
    assert r.status_code == 204
    # Old access token must now be rejected (token_version incremented)
    r = await client.get("/api/v1/auth/me", headers=bearer(token))
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# OIDC info (public endpoint)
# ---------------------------------------------------------------------------

async def test_oidc_info_disabled_by_default(client: AsyncClient) -> None:
    r = await client.get("/api/v1/auth/oidc/info")
    assert r.status_code == 200
    assert r.json()["enabled"] is False
