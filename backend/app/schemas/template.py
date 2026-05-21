import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ZoneTemplateRecordCreate(BaseModel):
    name: str = Field(..., description="Relative name: '@', 'www', 'mail', or FQDN. Use {zone} in content for zone placeholder.")
    type: str = Field(..., max_length=16)
    ttl: int = Field(3600, ge=60, le=2147483647)
    content: str


class ZoneTemplateRecordResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    type: str
    ttl: int
    content: str


class ZoneTemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: str | None = None
    records: list[ZoneTemplateRecordCreate] = Field(default_factory=list)


class ZoneTemplateUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=128)
    description: str | None = None
    records: list[ZoneTemplateRecordCreate] | None = None


class ZoneTemplateResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime
    records: list[ZoneTemplateRecordResponse]
