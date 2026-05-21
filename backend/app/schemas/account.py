import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.user import UserRole


class AccountCreate(BaseModel):
    name: str
    description: str | None = None


class AccountUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class AccountZoneAdd(BaseModel):
    zone_name: str


class AccountUserAdd(BaseModel):
    user_id: uuid.UUID
    role: UserRole

    @field_validator("role")
    @classmethod
    def role_must_be_operator_or_viewer(cls, v: UserRole) -> UserRole:
        if v not in (UserRole.operator, UserRole.viewer):
            raise ValueError("Account role must be 'operator' or 'viewer'")
        return v


class AccountUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    username: str
    role: UserRole


class AccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime
    zone_names: list[str]
    users: list[AccountUserResponse]
