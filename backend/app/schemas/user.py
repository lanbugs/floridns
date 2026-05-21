import re
import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.user import UserRole

_PASSWORD_RE = re.compile(r"^(?=.*[a-zA-Z])(?=.*\d).+$")


def _check_complexity(v: str) -> str:
    if not _PASSWORD_RE.match(v):
        raise ValueError("Password must contain at least one letter and one digit")
    return v


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    email: EmailStr
    password: str = Field(..., min_length=8)
    role: UserRole = UserRole.viewer

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return _check_complexity(v)


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    password: str | None = Field(None, min_length=8)
    current_password: str | None = None
    role: UserRole | None = None
    is_active: bool | None = None

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str | None) -> str | None:
        if v is not None:
            _check_complexity(v)
        return v


class UserResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    username: str
    email: str
    role: UserRole
    is_active: bool
    created_at: datetime
    totp_enabled: bool = False
    totp_required: bool = False   # computed at request time from global setting


class TotpSetupResponse(BaseModel):
    secret: str
    uri: str


class TotpEnableRequest(BaseModel):
    secret: str = Field(..., min_length=16, max_length=64)
    code: str = Field(..., min_length=6, max_length=6)


class TotpDisableRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=6)


class ApiKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    scope: str = Field("read-write", pattern="^(read-only|read-write|acme)$")
    zone_restriction: str | None = Field(None, max_length=255)


class ApiKeyResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    scope: str
    zone_restriction: str | None = None
    is_active: bool
    created_at: datetime


class ApiKeyCreatedResponse(ApiKeyResponse):
    key: str


class ZonePermissionCreate(BaseModel):
    zone_name: str
    role: UserRole

    @field_validator("zone_name")
    @classmethod
    def ensure_trailing_dot(cls, v: str) -> str:
        return v if v.endswith(".") else v + "."


class ZonePermissionResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    zone_name: str
    role: UserRole
