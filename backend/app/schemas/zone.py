import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ZoneCreate(BaseModel):
    name: str = Field(..., description="Zone name (FQDN with trailing dot)")
    kind: str = Field(..., pattern="^(Native|Master|Slave)$")
    nameservers: list[str] = Field(default_factory=list)
    masters: list[str] = Field(default_factory=list)
    account_id: uuid.UUID | None = None
    template_id: uuid.UUID | None = None
    comment: str | None = None


class ZoneUpdate(BaseModel):
    kind: str | None = Field(None, pattern="^(Native|Master|Slave)$")
    masters: list[str] | None = None
    comment: str | None = None


class RRSet(BaseModel):
    name: str
    type: str
    ttl: int = Field(..., ge=0, le=2147483647)
    records: list[dict[str, Any]]
    comments: list[dict[str, Any]] = Field(default_factory=list)


class ZoneSummary(BaseModel):
    id: str
    name: str
    kind: str
    serial: int | None = None
    last_check: int | None = None
    account: str | None = None
    dnssec: bool = False


class ZoneDetail(ZoneSummary):
    masters: list[str] = Field(default_factory=list)
    rrsets: list[RRSet] = Field(default_factory=list)
    can_edit: bool = False


class PaginatedZones(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[ZoneSummary]
