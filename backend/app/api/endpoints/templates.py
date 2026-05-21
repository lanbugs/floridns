import uuid
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select
from tenacity import RetryError

from app.api.deps import AdminRequired, CurrentUser, DbDep, PdnsDep, get_client_ip
from app.models.template import ZoneTemplate, ZoneTemplateRecord
from app.schemas.template import ZoneTemplateCreate, ZoneTemplateResponse, ZoneTemplateUpdate
from app.services.audit_service import log_action
from app.services.pdns_client import PdnsError

router = APIRouter(prefix="/templates", tags=["templates"])


def _build_rrsets(records: list[ZoneTemplateRecord], zone_name: str) -> list[dict[str, Any]]:
    """Resolve template records against a concrete zone name and group into PowerDNS rrsets."""
    zone_bare = zone_name.rstrip(".")
    grouped: dict[tuple[str, str, int], list[str]] = defaultdict(list)

    for rec in records:
        if rec.type == "SOA":
            continue

        if rec.name == "@":
            resolved_name = zone_name
        elif rec.name.endswith("."):
            resolved_name = rec.name
        else:
            resolved_name = f"{rec.name}.{zone_name}"

        resolved_content = rec.content.replace("{zone}", zone_name).replace("{zone_bare}", zone_bare)
        grouped[(resolved_name, rec.type, rec.ttl)].append(resolved_content)

    return [
        {
            "name": name,
            "type": type_,
            "ttl": ttl,
            "changetype": "REPLACE",
            "records": [{"content": c, "disabled": False} for c in contents],
        }
        for (name, type_, ttl), contents in grouped.items()
    ]


@router.get("", response_model=list[ZoneTemplateResponse], dependencies=[AdminRequired])
async def list_templates(db: DbDep) -> list[ZoneTemplate]:
    result = await db.execute(select(ZoneTemplate).order_by(ZoneTemplate.name))
    return list(result.scalars().all())


@router.post("", response_model=ZoneTemplateResponse, status_code=status.HTTP_201_CREATED, dependencies=[AdminRequired])
async def create_template(body: ZoneTemplateCreate, db: DbDep) -> ZoneTemplate:
    existing = (await db.execute(select(ZoneTemplate).where(ZoneTemplate.name == body.name))).scalar_one_or_none()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Template name already exists")

    template = ZoneTemplate(name=body.name, description=body.description)
    for r in body.records:
        template.records.append(ZoneTemplateRecord(name=r.name, type=r.type, ttl=r.ttl, content=r.content))

    db.add(template)
    await db.commit()
    await db.refresh(template)
    return template


@router.get("/{template_id}", response_model=ZoneTemplateResponse, dependencies=[AdminRequired])
async def get_template(template_id: uuid.UUID, db: DbDep) -> ZoneTemplate:
    template = (await db.execute(select(ZoneTemplate).where(ZoneTemplate.id == template_id))).scalar_one_or_none()
    if not template:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Template not found")
    return template


@router.put("/{template_id}", response_model=ZoneTemplateResponse, dependencies=[AdminRequired])
async def update_template(template_id: uuid.UUID, body: ZoneTemplateUpdate, db: DbDep) -> ZoneTemplate:
    template = (await db.execute(select(ZoneTemplate).where(ZoneTemplate.id == template_id))).scalar_one_or_none()
    if not template:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Template not found")

    if body.name is not None:
        conflict = (
            await db.execute(select(ZoneTemplate).where(ZoneTemplate.name == body.name, ZoneTemplate.id != template_id))
        ).scalar_one_or_none()
        if conflict:
            raise HTTPException(status.HTTP_409_CONFLICT, "Template name already exists")
        template.name = body.name

    if body.description is not None:
        template.description = body.description

    if body.records is not None:
        for rec in list(template.records):
            await db.delete(rec)
        template.records = [
            ZoneTemplateRecord(name=r.name, type=r.type, ttl=r.ttl, content=r.content)
            for r in body.records
        ]

    await db.commit()
    await db.refresh(template)
    return template


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[AdminRequired])
async def delete_template(template_id: uuid.UUID, db: DbDep) -> None:
    template = (await db.execute(select(ZoneTemplate).where(ZoneTemplate.id == template_id))).scalar_one_or_none()
    if not template:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Template not found")
    await db.delete(template)
    await db.commit()


@router.post("/{template_id}/apply/{zone_id}", status_code=status.HTTP_204_NO_CONTENT)
async def apply_template(
    template_id: uuid.UUID,
    zone_id: str,
    request: Request,
    current_user: CurrentUser,
    db: DbDep,
    pdns: PdnsDep,
) -> None:
    template = (await db.execute(select(ZoneTemplate).where(ZoneTemplate.id == template_id))).scalar_one_or_none()
    if not template:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Template not found")

    try:
        zone = await pdns.get_zone(zone_id)
    except (PdnsError, RetryError) as e:
        if isinstance(e, PdnsError):
            raise HTTPException(e.status_code, str(e))
        raise HTTPException(502, "PowerDNS unreachable")

    zone_name: str = zone["name"]
    rrsets = _build_rrsets(template.records, zone_name)
    if not rrsets:
        return

    try:
        await pdns.patch_rrsets(zone_id, {"rrsets": rrsets})
    except (PdnsError, RetryError) as e:
        if isinstance(e, PdnsError):
            raise HTTPException(e.status_code, str(e))
        raise HTTPException(502, "PowerDNS unreachable")

    await log_action(
        db,
        user=current_user,
        ip_address=get_client_ip(request),
        action="template.apply",
        resource_type="zone",
        resource_id=zone_name,
        after={"template": template.name, "rrsets_applied": len(rrsets)},
    )
    await db.commit()
