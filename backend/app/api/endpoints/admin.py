import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import AdminRequired, DbDep, PdnsDep
from app.models.account import Account, AccountUser, AccountZone
from app.models.user import User, ZonePermission
from app.services.dnssec_service import expiry_summary, get_rrsig_expiry

router = APIRouter(prefix="/admin", tags=["admin"])


class DirectPermission(BaseModel):
    zone_name: str
    role: str


class AccountPermission(BaseModel):
    account_id: str
    account_name: str
    member_role: str
    zones: list[str]


class UserPermissionSummary(BaseModel):
    id: str
    username: str
    email: str
    role: str
    is_active: bool
    direct_permissions: list[DirectPermission]
    account_permissions: list[AccountPermission]


@router.get("/permissions-overview", response_model=list[UserPermissionSummary], dependencies=[AdminRequired])
async def permissions_overview(db: DbDep) -> list[UserPermissionSummary]:
    users = (
        await db.execute(
            select(User).options(selectinload(User.zone_permissions)).order_by(User.username)
        )
    ).scalars().all()

    # Load all account memberships with their account names and zones in one pass
    au_rows = (
        await db.execute(
            select(AccountUser, Account.name, Account.id)
            .join(Account, AccountUser.account_id == Account.id)
        )
    ).all()

    # Map account_id → zones
    az_rows = (await db.execute(select(AccountZone))).scalars().all()
    account_zones: dict[uuid.UUID, list[str]] = {}
    for az in az_rows:
        account_zones.setdefault(az.account_id, []).append(az.zone_name)

    # Build per-user account membership map
    user_accounts: dict[uuid.UUID, list[dict[str, Any]]] = {}
    for au, acct_name, acct_id in au_rows:
        user_accounts.setdefault(au.user_id, []).append({
            "account_id": str(acct_id),
            "account_name": acct_name,
            "member_role": au.role.value,
            "zones": sorted(account_zones.get(acct_id, [])),
        })

    result: list[UserPermissionSummary] = []
    for user in users:
        direct = [
            DirectPermission(zone_name=zp.zone_name, role=zp.role.value)
            for zp in sorted(user.zone_permissions, key=lambda x: x.zone_name)
        ]
        accounts = [
            AccountPermission(**a)
            for a in user_accounts.get(user.id, [])
        ]
        result.append(UserPermissionSummary(
            id=str(user.id),
            username=user.username,
            email=user.email,
            role=user.role.value,
            is_active=user.is_active,
            direct_permissions=direct,
            account_permissions=accounts,
        ))

    return result


class DnssecExpiryEntry(BaseModel):
    zone: str
    expiry: str
    days_remaining: int
    warning: bool
    critical: bool


@router.get("/dnssec-expiry", response_model=list[DnssecExpiryEntry], dependencies=[AdminRequired])
async def dnssec_expiry_overview(pdns: PdnsDep) -> list[DnssecExpiryEntry]:
    """Return all DNSSEC-enabled zones with expiry info, ordered by soonest expiry first."""
    zones = await pdns.list_zones()
    dnssec_zones = [z["id"] for z in zones if z.get("dnssec")]

    async def _check(zone_id: str) -> dict[str, Any] | None:
        try:
            expiry = await asyncio.wait_for(get_rrsig_expiry(zone_id), timeout=5)
            summary = expiry_summary(expiry)
            if summary["expiry"] is None:
                return None
            return {"zone": zone_id, **summary}
        except Exception:
            return None

    results = await asyncio.gather(*[_check(z) for z in dnssec_zones])
    entries = [DnssecExpiryEntry(**r) for r in results if r is not None]
    return sorted(entries, key=lambda e: e.days_remaining)
