import csv
import io
import json
from typing import Any

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from app.api.deps import AdminRequired, CurrentUser, DbDep
from app.core.limiter import limiter
from app.schemas.audit import AuditLogResponse, PaginatedAuditLog
from app.services.audit_service import get_audit_logs

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=PaginatedAuditLog, dependencies=[AdminRequired])
async def list_audit_logs(
    current_user: CurrentUser,
    db: DbDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    action: str | None = None,
    resource_type: str | None = None,
    username: str | None = None,
) -> PaginatedAuditLog:
    total, rows = await get_audit_logs(
        db,
        page=page,
        page_size=page_size,
        action=action,
        resource_type=resource_type,
        username=username,
    )
    return PaginatedAuditLog(
        total=total,
        page=page,
        page_size=page_size,
        items=[AuditLogResponse.model_validate(r) for r in rows],
    )


@router.get("/export/csv", dependencies=[AdminRequired])
@limiter.limit("10/hour")
async def export_csv(request: Request, current_user: CurrentUser, db: DbDep) -> StreamingResponse:
    _, rows = await get_audit_logs(db, page=1, page_size=10000)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        ["timestamp", "username", "ip_address", "action", "resource_type", "resource_id", "comment"]
    )
    for row in rows:
        writer.writerow(
            [
                row.timestamp.isoformat(),
                row.username,
                row.ip_address,
                row.action,
                row.resource_type,
                row.resource_id or "",
                row.comment or "",
            ]
        )
    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit.csv"},
    )


@router.get("/export/json", dependencies=[AdminRequired])
@limiter.limit("10/hour")
async def export_json(request: Request, current_user: CurrentUser, db: DbDep) -> StreamingResponse:
    _, rows = await get_audit_logs(db, page=1, page_size=10000)
    data = [AuditLogResponse.model_validate(r).model_dump(mode="json") for r in rows]

    return StreamingResponse(
        iter([json.dumps(data, default=str)]),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=audit.json"},
    )
