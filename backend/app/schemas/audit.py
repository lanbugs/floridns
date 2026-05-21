import uuid
from datetime import datetime

from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    timestamp: datetime
    username: str
    ip_address: str
    action: str
    resource_type: str
    resource_id: str | None
    before_value: str | None
    after_value: str | None
    comment: str | None


class PaginatedAuditLog(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[AuditLogResponse]
