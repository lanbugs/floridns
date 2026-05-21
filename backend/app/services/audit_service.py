import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.user import User


async def log_action(
    db: AsyncSession,
    *,
    user: User | None,
    ip_address: str,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    before: Any = None,
    after: Any = None,
    comment: str | None = None,
) -> None:
    import json

    entry = AuditLog(
        user_id=user.id if user else None,
        username=user.username if user else "system",
        ip_address=ip_address,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        before_value=json.dumps(before) if before is not None else None,
        after_value=json.dumps(after) if after is not None else None,
        comment=comment,
    )
    db.add(entry)
    await db.flush()


async def get_audit_logs(
    db: AsyncSession,
    *,
    page: int = 1,
    page_size: int = 50,
    action: str | None = None,
    resource_type: str | None = None,
    username: str | None = None,
) -> tuple[int, list[AuditLog]]:
    query = select(AuditLog).order_by(AuditLog.timestamp.desc())

    if action:
        query = query.where(AuditLog.action == action)
    if resource_type:
        query = query.where(AuditLog.resource_type == resource_type)
    if username:
        query = query.where(AuditLog.username == username)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar_one()

    rows = (await db.execute(query.offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return total, list(rows)
