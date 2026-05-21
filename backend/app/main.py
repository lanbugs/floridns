import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.endpoints.nic import router as nic_router
from app.api.router import api_router
from app.core.config import settings
from app.core.limiter import limiter
from app.core.logging import configure_logging

configure_logging()
logger = structlog.get_logger(__name__)


async def _create_initial_admin() -> None:
    if not (settings.INITIAL_ADMIN_USERNAME and settings.INITIAL_ADMIN_PASSWORD and settings.INITIAL_ADMIN_EMAIL):
        return

    from sqlalchemy import func, select
    from app.core.database import AsyncSessionLocal
    from app.core.security import hash_password
    from app.models.user import User, UserRole

    async with AsyncSessionLocal() as db:
        count = (await db.execute(select(func.count()).select_from(User))).scalar_one()
        if count > 0:
            return

        user = User(
            username=settings.INITIAL_ADMIN_USERNAME,
            email=settings.INITIAL_ADMIN_EMAIL,
            hashed_password=hash_password(settings.INITIAL_ADMIN_PASSWORD),
            role=UserRole.superadmin,
        )
        db.add(user)
        await db.commit()
        logger.info("Initial admin user created", username=settings.INITIAL_ADMIN_USERNAME)


async def _purge_expired_tokens() -> None:
    from datetime import datetime as _dt, UTC as _UTC
    from sqlalchemy import delete
    from app.core.database import AsyncSessionLocal
    from app.models.refresh_token import RefreshTokenDenylist

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            delete(RefreshTokenDenylist).where(RefreshTokenDenylist.expires_at < _dt.now(_UTC))
        )
        await db.commit()
        if result.rowcount:
            logger.info("Purged expired refresh token denylist entries", count=result.rowcount)


async def _periodic_denylist_cleanup() -> None:
    while True:
        await asyncio.sleep(3600)  # once per hour
        try:
            await _purge_expired_tokens()
        except Exception as exc:
            logger.warning("Periodic denylist cleanup failed", error=str(exc))


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("FloriDNS starting", version="0.1.0", pdns_url=str(settings.PDNS_API_URL))
    await _create_initial_admin()
    await _purge_expired_tokens()
    cleanup_task = asyncio.create_task(_periodic_denylist_cleanup())
    yield
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    logger.info("FloriDNS shutting down")


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json" if settings.DOCS_ENABLED else None,
    docs_url=f"{settings.API_V1_STR}/docs" if settings.DOCS_ENABLED else None,
    redoc_url=f"{settings.API_V1_STR}/redoc" if settings.DOCS_ENABLED else None,
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)
app.include_router(nic_router)  # /nic/update — DynDNS 2 protocol, no API prefix


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    from app.services.pdns_client import PdnsClient, PdnsError

    pdns_status = "reachable"
    try:
        await PdnsClient().get_server_info()
    except PdnsError:
        pdns_status = "unreachable"
    except Exception:
        pdns_status = "unreachable"

    return {"status": "ok", "pdns": pdns_status}
