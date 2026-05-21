import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.setting import Setting
from app.models.zone_history import ZoneHistory
from app.services.pdns_client import PdnsClient


async def is_history_enabled(db: AsyncSession) -> bool:
    row = (await db.execute(select(Setting).where(Setting.key == "zone_history_enabled"))).scalar_one_or_none()
    if row is None:
        return False
    return json.loads(row.value) is True


async def capture_rrsets(pdns: PdnsClient, zone_id: str) -> list[dict[str, Any]]:
    zone = await pdns.get_zone(zone_id)
    return zone.get("rrsets", [])


async def save_history(
    db: AsyncSession,
    zone_name: str,
    action: str,
    username: str,
    before: list[dict[str, Any]],
    after: list[dict[str, Any]],
) -> ZoneHistory:
    entry = ZoneHistory(
        zone_name=zone_name,
        action=action,
        username=username,
        snapshot_before=before,
        snapshot_after=after,
    )
    db.add(entry)
    return entry


def build_restore_rrsets(
    snapshot: list[dict[str, Any]],
    current: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build a PATCH payload that restores a zone to the given snapshot."""
    snapshot_keys = {(r["name"], r["type"]) for r in snapshot}
    current_keys = {(r["name"], r["type"]) for r in current}

    ops: list[dict[str, Any]] = []

    # Delete rrsets present now but missing in snapshot (skip SOA)
    for name, rtype in current_keys - snapshot_keys:
        if rtype == "SOA":
            continue
        ops.append({"name": name, "type": rtype, "changetype": "DELETE"})

    # Replace all rrsets from snapshot
    for rrset in snapshot:
        if rrset.get("type") == "SOA":
            continue
        ops.append({
            "name": rrset["name"],
            "type": rrset["type"],
            "ttl": rrset["ttl"],
            "changetype": "REPLACE",
            "records": rrset.get("records", []),
            "comments": rrset.get("comments", []),
        })

    return ops
