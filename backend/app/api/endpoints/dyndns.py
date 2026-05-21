"""CRUD API for DynDNS host management (/api/v1/dyndns/hosts)."""
import json
import secrets
import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbDep, user_can_operate_zone
from app.core.security import hash_password, verify_password
from app.models.dyndns import DynDnsHost
from app.models.setting import Setting
from app.schemas.dyndns import DynDnsHostCreate, DynDnsHostCreated, DynDnsHostResponse, DynDnsHostUpdate

router = APIRouter(prefix="/dyndns/hosts", tags=["dyndns"])


def _token() -> str:
    return secrets.token_urlsafe(32)


async def _require_enabled(db: DbDep) -> None:
    row = (await db.execute(select(Setting).where(Setting.key == "dyndns_enabled"))).scalar_one_or_none()
    if row and not json.loads(row.value):
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Dynamic DNS is disabled")


@router.get("", response_model=list[DynDnsHostResponse])
async def list_hosts(current_user: CurrentUser, db: DbDep) -> list[DynDnsHost]:
    await _require_enabled(db)
    result = await db.execute(select(DynDnsHost).where(DynDnsHost.user_id == current_user.id))
    return list(result.scalars().all())


@router.post("", response_model=DynDnsHostCreated, status_code=status.HTTP_201_CREATED)
async def create_host(body: DynDnsHostCreate, current_user: CurrentUser, db: DbDep) -> DynDnsHostCreated:
    await _require_enabled(db)
    fqdn = f"{body.hostname}.{body.zone_name}"  # zone_name already has trailing dot
    if not await user_can_operate_zone(db, current_user, body.zone_name):
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"You do not have access to zone '{body.zone_name.rstrip('.')}'")
    existing = await db.execute(select(DynDnsHost).where(DynDnsHost.hostname == fqdn))
    if existing.scalar_one_or_none():
        raise HTTPException(status.HTTP_409_CONFLICT, f"Hostname '{fqdn}' is already registered")

    plain = _token()
    host = DynDnsHost(
        user_id=current_user.id,
        hostname=fqdn,
        zone_name=body.zone_name,
        description=body.description,
        token_hash=hash_password(plain),
    )
    db.add(host)
    await db.commit()
    await db.refresh(host)

    return DynDnsHostCreated(
        id=host.id,
        hostname=host.hostname,
        zone_name=host.zone_name,
        description=host.description,
        last_ip=host.last_ip,
        last_ip6=host.last_ip6,
        last_update=host.last_update,
        offline=host.offline,
        is_active=host.is_active,
        created_at=host.created_at,
        token=plain,
    )


@router.patch("/{host_id}", response_model=DynDnsHostResponse)
async def update_host(host_id: uuid.UUID, body: DynDnsHostUpdate, current_user: CurrentUser, db: DbDep) -> DynDnsHost:
    await _require_enabled(db)
    host = await _get_own_host(host_id, current_user.id, db)
    if body.description is not None:
        host.description = body.description
    if body.is_active is not None:
        host.is_active = body.is_active
    if body.offline is not None:
        host.offline = body.offline
    await db.commit()
    await db.refresh(host)
    return host


@router.post("/{host_id}/regenerate-token", response_model=DynDnsHostCreated)
async def regenerate_token(host_id: uuid.UUID, current_user: CurrentUser, db: DbDep) -> DynDnsHostCreated:
    await _require_enabled(db)
    host = await _get_own_host(host_id, current_user.id, db)
    plain = _token()
    host.token_hash = hash_password(plain)
    await db.commit()
    await db.refresh(host)

    return DynDnsHostCreated(
        id=host.id,
        hostname=host.hostname,
        zone_name=host.zone_name,
        description=host.description,
        last_ip=host.last_ip,
        last_ip6=host.last_ip6,
        last_update=host.last_update,
        offline=host.offline,
        is_active=host.is_active,
        created_at=host.created_at,
        token=plain,
    )


@router.delete("/{host_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_host(host_id: uuid.UUID, current_user: CurrentUser, db: DbDep) -> None:
    await _require_enabled(db)
    host = await _get_own_host(host_id, current_user.id, db)
    await db.delete(host)
    await db.commit()


async def _get_own_host(host_id: uuid.UUID, user_id: uuid.UUID, db) -> DynDnsHost:  # type: ignore[no-untyped-def]
    result = await db.execute(
        select(DynDnsHost).where(DynDnsHost.id == host_id, DynDnsHost.user_id == user_id)
    )
    host = result.scalar_one_or_none()
    if not host:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "DynDNS host not found")
    return host
