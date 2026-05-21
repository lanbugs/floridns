import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbDep, PdnsDep, get_client_ip, get_user_accessible_zone_names
from app.models.zone_history import ZoneHistory
from app.services.audit_service import log_action
from app.services.history_service import build_restore_rrsets, capture_rrsets, save_history
from app.services.pdns_client import PdnsError

router = APIRouter(prefix="/zones/{zone_id}/history", tags=["zone-history"])


class HistoryEntry(BaseModel):
    id: str
    zone_name: str
    action: str
    username: str
    created_at: str
    record_count_before: int
    record_count_after: int


class PaginatedHistory(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[HistoryEntry]


@router.get("", response_model=PaginatedHistory)
async def list_history(
    zone_id: str,
    current_user: CurrentUser,
    db: DbDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
) -> PaginatedHistory:
    allowed = await get_user_accessible_zone_names(db, current_user)
    if allowed is not None and zone_id not in allowed:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Access denied")

    total = (
        await db.execute(
            select(func.count()).select_from(ZoneHistory).where(ZoneHistory.zone_name == zone_id)
        )
    ).scalar_one()

    rows = (
        await db.execute(
            select(ZoneHistory)
            .where(ZoneHistory.zone_name == zone_id)
            .order_by(ZoneHistory.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()

    items = [
        HistoryEntry(
            id=str(r.id),
            zone_name=r.zone_name,
            action=r.action,
            username=r.username,
            created_at=r.created_at.isoformat(),
            record_count_before=len(r.snapshot_before),
            record_count_after=len(r.snapshot_after),
        )
        for r in rows
    ]

    return PaginatedHistory(total=total, page=page, page_size=page_size, items=items)


@router.get("/{history_id}/snapshot")
async def get_snapshot(
    zone_id: str,
    history_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbDep,
) -> dict[str, Any]:
    allowed = await get_user_accessible_zone_names(db, current_user)
    if allowed is not None and zone_id not in allowed:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Access denied")

    entry = (
        await db.execute(
            select(ZoneHistory).where(ZoneHistory.id == history_id, ZoneHistory.zone_name == zone_id)
        )
    ).scalar_one_or_none()
    if not entry:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "History entry not found")

    return {"before": entry.snapshot_before, "after": entry.snapshot_after}


@router.post("/{history_id}/restore", status_code=status.HTTP_204_NO_CONTENT)
async def restore_snapshot(
    zone_id: str,
    history_id: uuid.UUID,
    request: Request,
    current_user: CurrentUser,
    db: DbDep,
    pdns: PdnsDep,
) -> None:
    allowed = await get_user_accessible_zone_names(db, current_user)
    if allowed is not None and zone_id not in allowed:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Access denied")

    entry = (
        await db.execute(
            select(ZoneHistory).where(ZoneHistory.id == history_id, ZoneHistory.zone_name == zone_id)
        )
    ).scalar_one_or_none()
    if not entry:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "History entry not found")

    try:
        current = await capture_rrsets(pdns, zone_id)
        ops = build_restore_rrsets(entry.snapshot_before, current)
        if ops:
            await pdns.patch_rrsets(zone_id, {"rrsets": ops})
        after = await capture_rrsets(pdns, zone_id)
    except PdnsError as e:
        raise HTTPException(e.status_code, str(e))

    await save_history(db, zone_id, "zone.restore", current_user.username, current, after)
    await log_action(
        db,
        user=current_user,
        ip_address=get_client_ip(request),
        action="zone.restore",
        resource_type="zone",
        resource_id=zone_id,
        after={"restored_from": str(history_id)},
    )
    await db.commit()
