from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import CurrentUser, DbDep, PdnsDep
from app.models.zone_setting import ZoneSetting
from app.models.user import UserRole

router = APIRouter(prefix="/zones/{zone_id}/settings", tags=["zones"])


class ZoneSettingResponse(BaseModel):
    zone_name: str
    auto_ptr: bool


class ZoneSettingUpdate(BaseModel):
    auto_ptr: bool


@router.get("", response_model=ZoneSettingResponse)
async def get_zone_settings(zone_id: str, current_user: CurrentUser, db: DbDep, pdns: PdnsDep) -> ZoneSettingResponse:
    if current_user.role not in (UserRole.superadmin, UserRole.admin):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin required to view zone settings")

    row = (await db.execute(select(ZoneSetting).where(ZoneSetting.zone_name == zone_id))).scalar_one_or_none()
    return ZoneSettingResponse(zone_name=zone_id, auto_ptr=row.auto_ptr if row else False)


@router.put("", response_model=ZoneSettingResponse)
async def update_zone_settings(
    zone_id: str, body: ZoneSettingUpdate, current_user: CurrentUser, db: DbDep, pdns: PdnsDep
) -> ZoneSettingResponse:
    if current_user.role not in (UserRole.superadmin, UserRole.admin):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin required to change zone settings")

    row = (await db.execute(select(ZoneSetting).where(ZoneSetting.zone_name == zone_id))).scalar_one_or_none()
    if row is None:
        row = ZoneSetting(zone_name=zone_id, auto_ptr=body.auto_ptr)
        db.add(row)
    else:
        row.auto_ptr = body.auto_ptr
    await db.commit()
    return ZoneSettingResponse(zone_name=zone_id, auto_ptr=row.auto_ptr)
