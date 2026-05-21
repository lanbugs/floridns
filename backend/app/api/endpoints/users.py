import hashlib
import json
import secrets
import uuid

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbDep, SuperadminRequired
from app.core.limiter import limiter
from app.core.security import hash_password, verify_password
from app.models.passkey import Passkey
from app.models.setting import Setting
from app.models.user import ApiKey, User, UserRole, ZonePermission
from app.schemas.passkey import PasskeyRenameRequest, PasskeyResponse
from app.schemas.user import (
    ApiKeyCreate,
    ApiKeyCreatedResponse,
    ApiKeyResponse,
    TotpDisableRequest,
    TotpEnableRequest,
    TotpSetupResponse,
    UserCreate,
    UserResponse,
    UserUpdate,
    ZonePermissionCreate,
    ZonePermissionResponse,
)
from app.services.totp_service import generate_secret, get_provisioning_uri, verify_totp

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserResponse])
async def list_users(current_user: CurrentUser, db: DbDep) -> list[User]:
    if current_user.role not in (UserRole.superadmin, UserRole.admin):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")
    result = await db.execute(select(User).order_by(User.username))
    return list(result.scalars().all())


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreate,
    current_user: CurrentUser,
    db: DbDep,
) -> User:
    if current_user.role not in (UserRole.superadmin, UserRole.admin):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")
    if current_user.role == UserRole.admin and body.role == UserRole.superadmin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot create superadmin")

    existing = (
        await db.execute(select(User).where(User.username == body.username))
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Username already exists")

    user = User(
        username=body.username,
        email=body.email,
        hashed_password=hash_password(body.password),
        role=body.role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: CurrentUser, db: DbDep) -> dict:  # type: ignore[type-arg]
    require_setting = (
        await db.execute(select(Setting).where(Setting.key == "require_totp"))
    ).scalar_one_or_none()
    require_totp_global = json.loads(require_setting.value) if require_setting else False
    totp_required = bool(require_totp_global) and not current_user.totp_enabled
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "role": current_user.role,
        "is_active": current_user.is_active,
        "created_at": current_user.created_at,
        "totp_enabled": current_user.totp_enabled,
        "totp_required": totp_required,
    }


@router.get("/me/totp/setup", response_model=TotpSetupResponse)
async def totp_setup(current_user: CurrentUser) -> dict:  # type: ignore[type-arg]
    secret = generate_secret()
    uri = get_provisioning_uri(secret, current_user.username)
    return {"secret": secret, "uri": uri}


@router.post("/me/totp/enable", response_model=UserResponse)
async def totp_enable(body: TotpEnableRequest, current_user: CurrentUser, db: DbDep) -> dict:  # type: ignore[type-arg]
    if not verify_totp(body.secret, body.code):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid TOTP code — please try again")
    current_user.totp_secret = body.secret
    current_user.totp_enabled = True
    await db.commit()
    await db.refresh(current_user)
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "role": current_user.role,
        "is_active": current_user.is_active,
        "created_at": current_user.created_at,
        "totp_enabled": current_user.totp_enabled,
        "totp_required": False,
    }


@router.post("/me/totp/disable", response_model=UserResponse)
async def totp_disable(body: TotpDisableRequest, current_user: CurrentUser, db: DbDep) -> dict:  # type: ignore[type-arg]
    if not current_user.totp_enabled or not current_user.totp_secret:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "TOTP is not enabled")
    if not verify_totp(current_user.totp_secret, body.code):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid TOTP code — please try again")
    current_user.totp_secret = None
    current_user.totp_enabled = False
    await db.commit()
    await db.refresh(current_user)
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "role": current_user.role,
        "is_active": current_user.is_active,
        "created_at": current_user.created_at,
        "totp_enabled": current_user.totp_enabled,
        "totp_required": False,
    }


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: uuid.UUID, current_user: CurrentUser, db: DbDep) -> User:
    if current_user.role not in (UserRole.superadmin, UserRole.admin) and current_user.id != user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return user


@router.patch("/{user_id}", response_model=UserResponse)
@limiter.limit("10/minute")
async def update_user(
    user_id: uuid.UUID, body: UserUpdate, request: Request, current_user: CurrentUser, db: DbDep
) -> User:
    is_admin = current_user.role in (UserRole.superadmin, UserRole.admin)
    is_self = current_user.id == user_id

    if not is_admin and not is_self:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")

    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    if body.email is not None:
        user.email = body.email
    if body.password is not None:
        if is_self and not is_admin:
            if not body.current_password:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "current_password is required to change your password")
            if not user.hashed_password:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "Password change not supported for external auth accounts")
            if not verify_password(body.current_password, user.hashed_password):
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect")
        user.hashed_password = hash_password(body.password)
        user.token_version += 1  # invalidate all existing access tokens
    if body.role is not None and is_admin:
        user.role = body.role
    if body.is_active is not None and is_admin:
        user.is_active = body.is_active

    await db.commit()
    await db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: uuid.UUID, current_user: CurrentUser, db: DbDep, _: None = SuperadminRequired
) -> None:
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    await db.delete(user)
    await db.commit()


# --- API Keys ---


@router.post("/{user_id}/api-keys", response_model=ApiKeyCreatedResponse, status_code=201)
async def create_api_key(
    user_id: uuid.UUID, body: ApiKeyCreate, current_user: CurrentUser, db: DbDep
) -> dict:  # type: ignore[type-arg]
    if current_user.id != user_id and current_user.role not in (UserRole.superadmin, UserRole.admin):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")

    import bcrypt as _bcrypt

    raw_key = secrets.token_urlsafe(32)
    key_hash = _bcrypt.hashpw(raw_key.encode(), _bcrypt.gensalt(rounds=12)).decode()
    key_sha256 = hashlib.sha256(raw_key.encode()).hexdigest()

    api_key = ApiKey(
        user_id=user_id,
        name=body.name,
        key_hash=key_hash,
        key_sha256=key_sha256,
        scope=body.scope,
        zone_restriction=body.zone_restriction if body.scope == "acme" else None,
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)

    return {
        "id": api_key.id,
        "name": api_key.name,
        "scope": api_key.scope,
        "zone_restriction": api_key.zone_restriction,
        "is_active": api_key.is_active,
        "created_at": api_key.created_at,
        "key": raw_key,
    }


@router.get("/{user_id}/api-keys", response_model=list[ApiKeyResponse])
async def list_api_keys(user_id: uuid.UUID, current_user: CurrentUser, db: DbDep) -> list[ApiKey]:
    if current_user.id != user_id and current_user.role not in (UserRole.superadmin, UserRole.admin):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")
    result = await db.execute(select(ApiKey).where(ApiKey.user_id == user_id))
    return list(result.scalars().all())


@router.delete("/{user_id}/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_key(
    user_id: uuid.UUID, key_id: uuid.UUID, current_user: CurrentUser, db: DbDep
) -> None:
    if current_user.id != user_id and current_user.role not in (UserRole.superadmin, UserRole.admin):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")
    key = (
        await db.execute(select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user_id))
    ).scalar_one_or_none()
    if not key:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "API key not found")
    await db.delete(key)
    await db.commit()


# --- Zone Permissions ---


@router.post("/{user_id}/zone-permissions", response_model=ZonePermissionResponse, status_code=201)
async def add_zone_permission(
    user_id: uuid.UUID,
    body: ZonePermissionCreate,
    current_user: CurrentUser,
    db: DbDep,
) -> ZonePermission:
    if current_user.role not in (UserRole.superadmin, UserRole.admin):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")

    perm = ZonePermission(user_id=user_id, zone_name=body.zone_name, role=body.role)
    db.add(perm)
    await db.commit()
    await db.refresh(perm)
    return perm


@router.get("/{user_id}/zone-permissions", response_model=list[ZonePermissionResponse])
async def list_zone_permissions(
    user_id: uuid.UUID, current_user: CurrentUser, db: DbDep
) -> list[ZonePermission]:
    if current_user.role not in (UserRole.superadmin, UserRole.admin) and current_user.id != user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")
    result = await db.execute(select(ZonePermission).where(ZonePermission.user_id == user_id))
    return list(result.scalars().all())


@router.delete("/{user_id}/zone-permissions/{perm_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_zone_permission(
    user_id: uuid.UUID, perm_id: uuid.UUID, current_user: CurrentUser, db: DbDep
) -> None:
    if current_user.role not in (UserRole.superadmin, UserRole.admin):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")
    perm = (
        await db.execute(
            select(ZonePermission).where(
                ZonePermission.id == perm_id, ZonePermission.user_id == user_id
            )
        )
    ).scalar_one_or_none()
    if not perm:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Permission not found")
    await db.delete(perm)
    await db.commit()


# --- Passkeys ---


@router.get("/me/passkeys", response_model=list[PasskeyResponse])
async def list_my_passkeys(current_user: CurrentUser, db: DbDep) -> list[Passkey]:
    result = await db.execute(
        select(Passkey).where(Passkey.user_id == current_user.id).order_by(Passkey.created_at)
    )
    return list(result.scalars().all())


@router.patch("/me/passkeys/{passkey_id}", response_model=PasskeyResponse)
async def rename_passkey(
    passkey_id: uuid.UUID,
    body: PasskeyRenameRequest,
    current_user: CurrentUser,
    db: DbDep,
) -> Passkey:
    passkey = (
        await db.execute(
            select(Passkey).where(Passkey.id == passkey_id, Passkey.user_id == current_user.id)
        )
    ).scalar_one_or_none()
    if not passkey:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Passkey not found")
    passkey.name = body.name.strip() or None
    await db.commit()
    await db.refresh(passkey)
    return passkey


@router.delete("/me/passkeys/{passkey_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_passkey(
    passkey_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbDep,
) -> None:
    passkey = (
        await db.execute(
            select(Passkey).where(Passkey.id == passkey_id, Passkey.user_id == current_user.id)
        )
    ).scalar_one_or_none()
    if not passkey:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Passkey not found")
    await db.delete(passkey)
    await db.commit()
