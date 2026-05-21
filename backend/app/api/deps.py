import hashlib
import json
import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.encryption import decrypt_setting
from app.core.security import decode_token, verify_password
from app.models.account import AccountUser, AccountZone
from app.models.setting import Setting
from app.models.user import ApiKey, User, UserRole, ZonePermission
from app.services.pdns_client import PdnsClient

bearer = HTTPBearer(auto_error=False)

DbDep = Annotated[AsyncSession, Depends(get_db)]


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def _get_user_by_token(
    credentials: HTTPAuthorizationCredentials | None,
    db: AsyncSession,
    request: Request | None = None,
) -> User:
    if not credentials:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")

    token = credentials.credentials

    # Try JWT
    payload = decode_token(token)
    if payload and payload.get("type") == "access":
        user_id = payload.get("sub")
        if user_id:
            user = (
                await db.execute(
                    select(User).where(User.id == uuid.UUID(user_id), User.is_active == True)  # noqa: E712
                )
            ).scalar_one_or_none()
            if user:
                # Reject tokens that predate a token_version increment (logout/password-change)
                if payload.get("ver", 0) != user.token_version:
                    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session has been invalidated — please log in again")
                if request is not None:
                    request.state.api_key_scope = None
                    request.state.api_key_zone = None
                return user

    # Try API key — fast path: SHA-256 lookup (O(1))
    token_sha256 = hashlib.sha256(token.encode()).hexdigest()
    api_key = (
        await db.execute(
            select(ApiKey).where(ApiKey.key_sha256 == token_sha256, ApiKey.is_active == True)  # noqa: E712
        )
    ).scalar_one_or_none()

    # Legacy fallback: bcrypt scan for keys created before the SHA-256 column was added
    if api_key is None:
        import bcrypt as _bcrypt

        legacy_keys = (
            await db.execute(
                select(ApiKey).where(ApiKey.key_sha256.is_(None), ApiKey.is_active == True)  # noqa: E712
            )
        ).scalars().all()
        for candidate in legacy_keys:
            if _bcrypt.checkpw(token.encode(), candidate.key_hash.encode()):
                # Migrate on first use: store SHA-256 for next time
                candidate.key_sha256 = token_sha256
                await db.commit()
                api_key = candidate
                break

    if api_key is not None:
        user = (
            await db.execute(
                select(User).where(User.id == api_key.user_id, User.is_active == True)  # noqa: E712
            )
        ).scalar_one_or_none()
        if user:
            if request is not None:
                request.state.api_key_scope = api_key.scope
                request.state.api_key_zone = api_key.zone_restriction
            return user

    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    request: Request,
    db: DbDep,
) -> User:
    return await _get_user_by_token(credentials, db, request)


def get_api_key_scope(request: Request) -> str | None:
    return getattr(request.state, "api_key_scope", None)


def get_api_key_zone(request: Request) -> str | None:
    return getattr(request.state, "api_key_zone", None)


ApiKeyScopeDep = Annotated[str | None, Depends(get_api_key_scope)]
ApiKeyZoneDep = Annotated[str | None, Depends(get_api_key_zone)]


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*roles: UserRole):  # type: ignore[no-untyped-def]
    async def _check(user: CurrentUser) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")
        return user

    return Depends(_check)


AdminRequired = require_role(UserRole.superadmin, UserRole.admin)
SuperadminRequired = require_role(UserRole.superadmin)


async def get_pdns_client(db: DbDep) -> PdnsClient:
    row = (
        await db.execute(select(Setting).where(Setting.key == "pdns_primary"))
    ).scalar_one_or_none()
    if row is not None:
        decrypted = decrypt_setting("pdns_primary", row.value, settings.SETTINGS_ENCRYPTION_KEY)
        cfg: dict = json.loads(decrypted)
        return PdnsClient(
            url=cfg.get("url"),
            api_key=cfg.get("api_key"),
            ssl_verify=cfg.get("ssl_verify", True),
        )
    return PdnsClient()


PdnsDep = Annotated[PdnsClient, Depends(get_pdns_client)]


async def get_user_accessible_zone_names(db: AsyncSession, user: User) -> set[str] | None:
    """None means unrestricted (admin). Otherwise returns set of allowed zone names."""
    if user.role in (UserRole.superadmin, UserRole.admin):
        return None
    allowed: set[str] = set()
    direct = await db.execute(select(ZonePermission.zone_name).where(ZonePermission.user_id == user.id))
    allowed.update(direct.scalars().all())
    acct_zones = await db.execute(
        select(AccountZone.zone_name)
        .join(AccountUser, AccountZone.account_id == AccountUser.account_id)
        .where(AccountUser.user_id == user.id)
    )
    allowed.update(acct_zones.scalars().all())
    return allowed


async def user_can_operate_zone(db: AsyncSession, user: User, zone_name: str) -> bool:
    """True if user has operator or higher access to this zone (directly or via account)."""
    if user.role in (UserRole.superadmin, UserRole.admin):
        return True
    # Normalize: always compare with trailing dot
    if not zone_name.endswith("."):
        zone_name = zone_name + "."
    # Direct operator permission
    direct = (await db.execute(
        select(ZonePermission).where(
            ZonePermission.user_id == user.id,
            ZonePermission.zone_name == zone_name,
            ZonePermission.role.in_([UserRole.operator, UserRole.admin, UserRole.superadmin]),
        )
    )).scalar_one_or_none()
    if direct:
        return True
    # Account-based operator permission
    acct = (await db.execute(
        select(AccountUser)
        .join(AccountZone, AccountUser.account_id == AccountZone.account_id)
        .where(
            AccountUser.user_id == user.id,
            AccountUser.role.in_([UserRole.operator, UserRole.admin, UserRole.superadmin]),
            AccountZone.zone_name == zone_name,  # already normalized above
        )
    )).scalar_one_or_none()
    return acct is not None
