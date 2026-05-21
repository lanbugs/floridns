from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.deps import get_db, get_pdns_client
from app.core.limiter import limiter
from app.core.security import hash_password
from app.main import app

# Disable rate limiting globally for tests
limiter.enabled = False
from app.models.base import Base
from app.models.user import User, UserRole

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture(autouse=True, scope="session")
async def setup_db() -> AsyncGenerator[None, None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        yield session


@pytest.fixture(autouse=True)
async def clean_tables(db: AsyncSession) -> AsyncGenerator[None, None]:
    yield
    for table in reversed(Base.metadata.sorted_tables):
        await db.execute(table.delete())
    await db.commit()


def _make_pdns_mock() -> MagicMock:
    m = MagicMock()
    m.list_zones = AsyncMock(return_value=[
        {"id": "example.com.", "name": "example.com.", "kind": "Master",
         "serial": 2024010101, "last_check": None, "account": "", "dnssec": False},
    ])
    m.get_zone = AsyncMock(return_value={
        "id": "example.com.", "name": "example.com.", "kind": "Master",
        "serial": 2024010101, "last_check": None, "account": "", "dnssec": False,
        "masters": [], "rrsets": [],
    })
    m.create_zone = AsyncMock(return_value={
        "id": "newzone.com.", "name": "newzone.com.", "kind": "Master",
        "serial": 1, "last_check": None, "account": "", "dnssec": False,
    })
    m.update_zone = AsyncMock(return_value=None)
    m.delete_zone = AsyncMock(return_value=None)
    m.patch_rrsets = AsyncMock(return_value=None)
    m.get_cryptokeys = AsyncMock(return_value=[])
    m.enable_dnssec = AsyncMock(return_value=None)
    m.disable_dnssec = AsyncMock(return_value=None)
    m.export_zone = AsyncMock(return_value="; Zone export: example.com.\n")
    m.get_stats = AsyncMock(return_value=[{"name": "uptime", "type": "StatisticItem", "value": "100"}])
    m.search = AsyncMock(return_value=[])
    return m


@pytest.fixture
def pdns_mock() -> MagicMock:
    return _make_pdns_mock()


@pytest.fixture
async def client(db: AsyncSession, pdns_mock: MagicMock) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db

    async def override_get_pdns() -> MagicMock:
        return pdns_mock

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_pdns_client] = override_get_pdns
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# User fixtures
# ---------------------------------------------------------------------------

async def _create_user(db: AsyncSession, username: str, role: UserRole, password: str = "pass1234") -> User:
    user = User(
        username=username,
        email=f"{username}@example.com",
        hashed_password=hash_password(password),
        role=role,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def superadmin(db: AsyncSession) -> User:
    return await _create_user(db, "superadmin", UserRole.superadmin)


@pytest.fixture
async def admin(db: AsyncSession) -> User:
    return await _create_user(db, "admin", UserRole.admin)


@pytest.fixture
async def operator(db: AsyncSession) -> User:
    return await _create_user(db, "operator", UserRole.operator)


@pytest.fixture
async def viewer(db: AsyncSession) -> User:
    return await _create_user(db, "viewer", UserRole.viewer)


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------

async def get_token(client: AsyncClient, username: str, password: str = "pass1234") -> str:
    r = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
