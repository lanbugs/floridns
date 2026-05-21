from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select
from tenacity import RetryError

from app.api.deps import ApiKeyZoneDep, ApiKeyScopeDep, CurrentUser, DbDep, PdnsDep, get_client_ip, user_can_operate_zone
from app.models.zone_setting import ZoneSetting
from app.schemas.record import BulkRecordOperation, RecordSetCreate
from app.services.audit_service import log_action
from app.services.auto_ptr_service import apply_auto_ptr
from app.services.dns_validator import normalize_record_content, validate_record
from app.services.history_service import capture_rrsets, is_history_enabled, save_history
from app.services.pdns_client import PdnsError

router = APIRouter(prefix="/zones/{zone_id}/records", tags=["records"])


@router.patch("", status_code=status.HTTP_204_NO_CONTENT)
async def patch_records(
    zone_id: str,
    body: BulkRecordOperation,
    request: Request,
    current_user: CurrentUser,
    db: DbDep,
    pdns: PdnsDep,
    api_key_scope: ApiKeyScopeDep,
    api_key_zone: ApiKeyZoneDep,
) -> None:
    if not await user_can_operate_zone(db, current_user, zone_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions for this zone")

    if api_key_scope == "acme":
        # Zone restriction check
        if api_key_zone and zone_id.rstrip(".") != api_key_zone.rstrip("."):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"ACME key is restricted to zone '{api_key_zone}'",
            )
        for op in body.rrsets:
            name = op.name.rstrip(".")
            if not name.startswith("_acme-challenge."):
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN,
                    "ACME key may only modify _acme-challenge TXT records",
                )
            if op.type.upper() != "TXT":
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN,
                    "ACME key may only modify TXT records",
                )

    rrsets: list[dict[str, Any]] = []

    for op in body.rrsets:
        if isinstance(op, RecordSetCreate):
            for record in op.records:
                validate_record(op.type, record.content, op.ttl)
            rrsets.append(
                {
                    "name": op.name,
                    "type": op.type,
                    "ttl": op.ttl,
                    "changetype": "REPLACE",
                    "records": [{"content": normalize_record_content(op.type, r.content), "disabled": r.disabled} for r in op.records],
                    "comments": (
                        [{"content": op.comment, "account": current_user.username}]
                        if op.comment
                        else []
                    ),
                }
            )
        else:
            rrsets.append({"name": op.name, "type": op.type, "changetype": "DELETE"})

    history_on = await is_history_enabled(db)
    zone_setting = (await db.execute(select(ZoneSetting).where(ZoneSetting.zone_name == zone_id))).scalar_one_or_none()
    auto_ptr = zone_setting.auto_ptr if zone_setting else False

    snapshot_before = await capture_rrsets(pdns, zone_id) if (history_on or auto_ptr) else []

    try:
        await pdns.patch_rrsets(zone_id, {"rrsets": rrsets})
    except (PdnsError, RetryError) as e:
        if isinstance(e, PdnsError):
            raise HTTPException(e.status_code, str(e))
        cause = e.__cause__
        if isinstance(cause, PdnsError):
            raise HTTPException(cause.status_code, str(cause))
        raise HTTPException(502, "PowerDNS unreachable")

    if history_on:
        snapshot_after = await capture_rrsets(pdns, zone_id)
        await save_history(db, zone_id, "records.patch", current_user.username, snapshot_before, snapshot_after)

    if auto_ptr:
        await apply_auto_ptr(pdns, zone_id, rrsets, snapshot_before)

    audit_ops = []
    for rs in rrsets:
        if rs["changetype"] == "DELETE":
            audit_ops.append({"op": "delete", "name": rs["name"], "type": rs["type"]})
        else:
            audit_ops.append({
                "op": "replace",
                "name": rs["name"],
                "type": rs["type"],
                "ttl": rs.get("ttl"),
                "records": [r["content"] for r in rs.get("records", [])],
                **({"comment": rs["comments"][0]["content"]} if rs.get("comments") else {}),
            })

    await log_action(
        db,
        user=current_user,
        ip_address=get_client_ip(request),
        action="records.patch",
        resource_type="zone",
        resource_id=zone_id,
        after={"operations": audit_ops},
    )
    await db.commit()
