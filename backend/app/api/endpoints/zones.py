from typing import Any

from fastapi import APIRouter, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from tenacity import RetryError

from app.api.deps import AdminRequired, CurrentUser, DbDep, PdnsDep, get_client_ip, get_user_accessible_zone_names, user_can_operate_zone
from app.models.account import Account, AccountZone
from app.models.template import ZoneTemplate
from app.api.endpoints.templates import _build_rrsets
from app.schemas.zone import ZoneCreate, ZoneDetail, ZoneSummary, PaginatedZones, ZoneUpdate
from app.services.audit_service import log_action
from app.services.dns_validator import ensure_trailing_dot, normalize_zone_name
from app.services.dnssec_service import expiry_summary, get_rrsig_expiry
from app.services.pdns_client import PdnsError
from app.services.zone_import import ParsedZone, parse_bind, parse_csv, to_rrsets


def _pdns_exc(e: Exception) -> HTTPException:
    if isinstance(e, PdnsError):
        return HTTPException(e.status_code, str(e))
    if isinstance(e, RetryError) and e.__cause__ and isinstance(e.__cause__, PdnsError):
        cause: PdnsError = e.__cause__
        return HTTPException(cause.status_code, str(cause))
    return HTTPException(502, "PowerDNS unreachable")

router = APIRouter(prefix="/zones", tags=["zones"])


def _pdns_to_summary(z: dict[str, Any]) -> ZoneSummary:
    return ZoneSummary(
        id=z["id"],
        name=z["name"],
        kind=z["kind"],
        serial=z.get("serial"),
        last_check=z.get("last_check"),
        account=z.get("account"),
        dnssec=z.get("dnssec", False),
    )


@router.get("", response_model=PaginatedZones)
async def list_zones(
    current_user: CurrentUser,
    db: DbDep,
    pdns: PdnsDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    search: str | None = None,
    kind: str | None = None,
) -> PaginatedZones:
    try:
        all_zones = await pdns.list_zones()
    except (PdnsError, RetryError) as e:
        raise _pdns_exc(e)

    allowed = await get_user_accessible_zone_names(db, current_user)
    if allowed is not None:
        all_zones = [z for z in all_zones if z["name"] in allowed]

    if search:
        all_zones = [z for z in all_zones if search.lower() in z["name"].lower()]
    if kind:
        all_zones = [z for z in all_zones if z.get("kind", "").lower() == kind.lower()]

    total = len(all_zones)
    start = (page - 1) * page_size
    items = [_pdns_to_summary(z) for z in all_zones[start : start + page_size]]

    return PaginatedZones(total=total, page=page, page_size=page_size, items=items)


@router.post("", response_model=ZoneSummary, status_code=status.HTTP_201_CREATED)
async def create_zone(
    body: ZoneCreate,
    request: Request,
    current_user: CurrentUser,
    db: DbDep,
    pdns: PdnsDep,
    _admin: Any = AdminRequired,
) -> ZoneSummary:
    zone_name = normalize_zone_name(body.name)
    nameservers = [ensure_trailing_dot(ns.strip()) for ns in body.nameservers if ns.strip()]

    rrsets: list[dict] = []
    if nameservers:
        primary_ns = nameservers[0]
        admin_email = f"hostmaster.{zone_name}"
        soa_content = f"{primary_ns} {admin_email} 1 10800 3600 604800 3600"
        rrsets.append({
            "name": zone_name,
            "type": "SOA",
            "ttl": 3600,
            "changetype": "REPLACE",
            "records": [{"content": soa_content, "disabled": False}],
        })

    account_name: str | None = None
    if body.account_id is not None:
        account = (
            await db.execute(select(Account).where(Account.id == body.account_id))
        ).scalar_one_or_none()
        if not account:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Account not found")
        account_name = account.name

    payload = {
        "name": zone_name,
        "kind": body.kind,
        "nameservers": nameservers,
        "masters": body.masters,
        "rrsets": rrsets,
        **({"account": account_name} if account_name else {}),
    }
    try:
        zone = await pdns.create_zone(payload)
    except (PdnsError, RetryError) as e:
        raise _pdns_exc(e)

    if body.account_id is not None:
        db.add(AccountZone(account_id=body.account_id, zone_name=zone_name))

    if body.template_id is not None:
        template = (
            await db.execute(select(ZoneTemplate).where(ZoneTemplate.id == body.template_id))
        ).scalar_one_or_none()
        if template and template.records:
            template_rrsets = _build_rrsets(template.records, zone_name)

            # Determine the primary NS for the SOA:
            # If nameservers were explicitly provided use the first one, otherwise try
            # to derive it from any NS record at the zone apex in the template.
            primary_ns: str | None = nameservers[0] if nameservers else None
            if primary_ns is None:
                zone_bare = zone_name.rstrip(".")
                for rec in template.records:
                    if rec.type == "NS" and rec.name in ("@", zone_name, zone_bare):
                        candidate = rec.content.replace("{zone}", zone_name).replace("{zone_bare}", zone_bare)
                        primary_ns = ensure_trailing_dot(candidate)
                        break

            if primary_ns:
                soa_content = f"{primary_ns} hostmaster.{zone_name} 1 10800 3600 604800 3600"
                template_rrsets.append({
                    "name": zone_name,
                    "type": "SOA",
                    "ttl": 3600,
                    "changetype": "REPLACE",
                    "records": [{"content": soa_content, "disabled": False}],
                })

            if template_rrsets:
                try:
                    await pdns.patch_rrsets(zone["id"], {"rrsets": template_rrsets})
                except (PdnsError, RetryError):
                    pass  # zone was created — don't fail the whole request over template records

    await log_action(
        db,
        user=current_user,
        ip_address=get_client_ip(request),
        action="zone.create",
        resource_type="zone",
        resource_id=zone["name"],
        after=payload,
        comment=body.comment,
    )
    await db.commit()
    return _pdns_to_summary(zone)


@router.get("/{zone_id}", response_model=ZoneDetail)
async def get_zone(zone_id: str, current_user: CurrentUser, db: DbDep, pdns: PdnsDep) -> ZoneDetail:
    try:
        z = await pdns.get_zone(zone_id)
    except (PdnsError, RetryError) as e:
        raise _pdns_exc(e)

    allowed = await get_user_accessible_zone_names(db, current_user)
    if allowed is not None and z["name"] not in allowed:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Access denied")

    can_edit = await user_can_operate_zone(db, current_user, z["name"])

    return ZoneDetail(
        id=z["id"],
        name=z["name"],
        kind=z["kind"],
        serial=z.get("serial"),
        last_check=z.get("last_check"),
        account=z.get("account"),
        dnssec=z.get("dnssec", False),
        masters=z.get("masters", []),
        rrsets=z.get("rrsets", []),
        can_edit=can_edit,
    )


@router.put("/{zone_id}", response_model=ZoneSummary)
async def update_zone(
    zone_id: str,
    body: ZoneUpdate,
    request: Request,
    current_user: CurrentUser,
    db: DbDep,
    pdns: PdnsDep,
    _admin: Any = AdminRequired,
) -> ZoneSummary:
    try:
        before = await pdns.get_zone(zone_id)
    except (PdnsError, RetryError) as e:
        raise _pdns_exc(e)

    patch: dict[str, Any] = {}
    if body.kind is not None:
        patch["kind"] = body.kind
    if body.masters is not None:
        patch["masters"] = body.masters

    try:
        await pdns.update_zone(zone_id, patch)
        after = await pdns.get_zone(zone_id)
    except (PdnsError, RetryError) as e:
        raise _pdns_exc(e)

    await log_action(
        db,
        user=current_user,
        ip_address=get_client_ip(request),
        action="zone.update",
        resource_type="zone",
        resource_id=zone_id,
        before=before,
        after=after,
        comment=body.comment,
    )
    await db.commit()
    return _pdns_to_summary(after)


@router.delete("/{zone_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_zone(
    zone_id: str,
    request: Request,
    current_user: CurrentUser,
    db: DbDep,
    pdns: PdnsDep,
    _admin: Any = AdminRequired,
) -> None:
    try:
        before = await pdns.get_zone(zone_id)
        await pdns.delete_zone(zone_id)
    except (PdnsError, RetryError) as e:
        raise _pdns_exc(e)

    await log_action(
        db,
        user=current_user,
        ip_address=get_client_ip(request),
        action="zone.delete",
        resource_type="zone",
        resource_id=zone_id,
        before=before,
    )
    await db.commit()


@router.get("/{zone_id}/export", response_class=PlainTextResponse)
async def export_zone(zone_id: str, current_user: CurrentUser, db: DbDep, pdns: PdnsDep) -> str:
    try:
        z = await pdns.get_zone(zone_id)
    except (PdnsError, RetryError) as e:
        raise _pdns_exc(e)

    allowed = await get_user_accessible_zone_names(db, current_user)
    if allowed is not None and z["name"] not in allowed:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Access denied")

    lines = [f"; Zone export: {z['name']}", f"; Serial: {z.get('serial', 0)}", ""]
    for rrset in z.get("rrsets", []):
        for record in rrset.get("records", []):
            if not record.get("disabled"):
                lines.append(f"{rrset['name']}\t{rrset['ttl']}\tIN\t{rrset['type']}\t{record['content']}")
    return "\n".join(lines)


@router.get("/{zone_id}/dnssec")
async def get_dnssec(zone_id: str, current_user: CurrentUser, db: DbDep, pdns: PdnsDep) -> Any:
    allowed = await get_user_accessible_zone_names(db, current_user)
    if allowed is not None and zone_id not in allowed:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Access denied")
    try:
        return await pdns.get_dnssec(zone_id)
    except (PdnsError, RetryError) as e:
        raise _pdns_exc(e)


@router.get("/{zone_id}/dnssec/expiry")
async def get_dnssec_expiry(zone_id: str, current_user: CurrentUser, db: DbDep) -> dict[str, Any]:
    allowed = await get_user_accessible_zone_names(db, current_user)
    if allowed is not None and zone_id not in allowed:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Access denied")
    expiry = await get_rrsig_expiry(zone_id)
    return expiry_summary(expiry)


@router.post("/{zone_id}/dnssec/enable", status_code=status.HTTP_204_NO_CONTENT)
async def enable_dnssec(
    zone_id: str,
    request: Request,
    current_user: CurrentUser,
    db: DbDep,
    pdns: PdnsDep,
    _admin: Any = AdminRequired,
) -> None:
    try:
        await pdns.enable_dnssec(zone_id)
    except (PdnsError, RetryError) as e:
        raise _pdns_exc(e)

    await log_action(
        db,
        user=current_user,
        ip_address=get_client_ip(request),
        action="dnssec.enable",
        resource_type="zone",
        resource_id=zone_id,
    )
    await db.commit()


@router.post("/import", dependencies=[AdminRequired])
async def import_zone(
    request: Request,
    current_user: CurrentUser,
    db: DbDep,
    pdns: PdnsDep,
    file: UploadFile,
    format: str = Form(...),        # "bind" or "csv"
    zone_name: str = Form(""),      # required for CSV; optional hint for BIND
    kind: str = Form("Master"),
    dry_run: bool = Form(False),
) -> dict[str, Any]:
    if format not in ("bind", "csv"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "format must be 'bind' or 'csv'")
    if kind not in ("Native", "Master", "Slave"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "kind must be Native, Master, or Slave")

    raw = (await file.read()).decode("utf-8", errors="replace")

    try:
        if format == "bind":
            parsed: ParsedZone = parse_bind(raw, hint_zone_name=zone_name or None)
        else:
            if not zone_name:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "zone_name is required for CSV import")
            parsed = parse_csv(raw, zone_name)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))

    rrsets = to_rrsets(parsed)

    # Check whether zone already exists
    try:
        existing_zones = await pdns.list_zones()
    except (PdnsError, RetryError) as e:
        raise _pdns_exc(e)
    already_exists = any(z["id"] == parsed.name or z["name"] == parsed.name for z in existing_zones)

    preview = [
        {"name": rs["name"], "type": rs["type"], "ttl": rs["ttl"], "record_count": len(rs["records"])}
        for rs in rrsets
    ]

    if dry_run:
        return {
            "zone_name": parsed.name,
            "kind": kind,
            "already_exists": already_exists,
            "rrset_count": len(rrsets),
            "record_count": sum(len(rs["records"]) for rs in rrsets),
            "errors": parsed.errors,
            "preview": preview,
        }

    # --- Perform actual import ---
    try:
        if not already_exists:
            await pdns.create_zone({
                "name": parsed.name,
                "kind": kind,
                "nameservers": [],
                "rrsets": rrsets,
            })
        else:
            await pdns.patch_rrsets(parsed.name, {"rrsets": rrsets})
    except (PdnsError, RetryError) as e:
        raise _pdns_exc(e)

    await log_action(
        db,
        user=current_user,
        ip_address=get_client_ip(request),
        action="zone.import",
        resource_type="zone",
        resource_id=parsed.name,
        after={"format": format, "rrset_count": len(rrsets), "already_exists": already_exists},
    )
    await db.commit()

    return {
        "zone_name": parsed.name,
        "kind": kind,
        "already_exists": already_exists,
        "rrset_count": len(rrsets),
        "record_count": sum(len(rs["records"]) for rs in rrsets),
        "errors": parsed.errors,
        "preview": [],
    }


@router.post("/{zone_id}/dnssec/disable", status_code=status.HTTP_204_NO_CONTENT)
async def disable_dnssec(
    zone_id: str,
    request: Request,
    current_user: CurrentUser,
    db: DbDep,
    pdns: PdnsDep,
    _admin: Any = AdminRequired,
) -> None:
    try:
        await pdns.disable_dnssec(zone_id)
    except (PdnsError, RetryError) as e:
        raise _pdns_exc(e)

    await log_action(
        db,
        user=current_user,
        ip_address=get_client_ip(request),
        action="dnssec.disable",
        resource_type="zone",
        resource_id=zone_id,
    )
    await db.commit()
