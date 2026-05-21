import json
from typing import Any

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import AdminRequired, SuperadminRequired, CurrentUser, DbDep
from app.core.config import settings
from app.core.encryption import decrypt_setting, encrypt_setting
from app.models.setting import Setting
from app.schemas.setting import SettingUpsert

router = APIRouter(prefix="/settings", tags=["settings"])

# Valid setting keys
_VALID_KEYS: set[str] = {
    "allowed_record_types_operator",
    "allowed_record_types_viewer",
    "slave_servers",
    "pdns_primary",
    "zone_history_enabled",
    "require_totp",
    "ldap_config",
    "oidc_config",
    "dyndns_enabled",
}


@router.get("/public")
async def get_public_settings(current_user: CurrentUser, db: DbDep) -> dict[str, Any]:
    """Feature flags accessible to all authenticated users."""
    row = (await db.execute(select(Setting).where(Setting.key == "dyndns_enabled"))).scalar_one_or_none()
    return {"dyndns_enabled": json.loads(row.value) if row else True}


@router.get("", dependencies=[SuperadminRequired])
async def get_settings(
    current_user: CurrentUser,
    db: DbDep,
) -> dict[str, Any]:
    result = await db.execute(select(Setting))
    rows = result.scalars().all()
    enc_key = settings.SETTINGS_ENCRYPTION_KEY
    out: dict[str, Any] = {}
    for row in rows:
        decrypted = decrypt_setting(row.key, row.value, enc_key)
        out[row.key] = json.loads(decrypted)
    return out


@router.put("/{key}", dependencies=[SuperadminRequired], status_code=status.HTTP_200_OK)
async def upsert_setting(
    key: str,
    body: SettingUpsert,
    current_user: CurrentUser,
    db: DbDep,
) -> dict[str, Any]:
    if key not in _VALID_KEYS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Unknown setting key: {key!r}")

    existing = (await db.execute(select(Setting).where(Setting.key == key))).scalar_one_or_none()

    serialized = json.dumps(body.value)
    stored = encrypt_setting(key, serialized, settings.SETTINGS_ENCRYPTION_KEY)

    if existing is None:
        db.add(Setting(key=key, value=stored, updated_by=current_user.username))
    else:
        existing.value = stored
        existing.updated_by = current_user.username

    await db.commit()
    return {key: body.value}
