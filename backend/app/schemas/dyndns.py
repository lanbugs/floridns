import re
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

_LABEL_RE = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?$")


class DynDnsHostCreate(BaseModel):
    hostname: str = Field(..., min_length=1, max_length=63, description="DNS label only, e.g. 'home'")
    zone_name: str = Field(..., min_length=3, max_length=253)
    description: str | None = Field(None, max_length=255)

    @field_validator("hostname")
    @classmethod
    def validate_label(cls, v: str) -> str:
        if "." in v:
            raise ValueError("hostname must be a single DNS label without dots — the zone is appended automatically")
        if not _LABEL_RE.match(v):
            raise ValueError("hostname must contain only letters, digits, and hyphens, and may not start or end with a hyphen")
        return v.lower()

    @field_validator("zone_name")
    @classmethod
    def ensure_zone_trailing_dot(cls, v: str) -> str:
        return v if v.endswith(".") else v + "."


class DynDnsHostUpdate(BaseModel):
    description: str | None = Field(None, max_length=255)
    is_active: bool | None = None
    offline: bool | None = None


class DynDnsHostResponse(BaseModel):
    id: uuid.UUID
    hostname: str
    zone_name: str
    description: str | None
    last_ip: str | None
    last_ip6: str | None
    last_update: datetime | None
    offline: bool
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class DynDnsHostCreated(DynDnsHostResponse):
    token: str
