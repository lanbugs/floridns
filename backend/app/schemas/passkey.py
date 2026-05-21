import uuid
from datetime import datetime

from pydantic import BaseModel


class PasskeyResponse(BaseModel):
    id: uuid.UUID
    name: str | None
    transports: str | None
    created_at: datetime
    last_used_at: datetime | None

    model_config = {"from_attributes": True}


class PasskeyRenameRequest(BaseModel):
    name: str


class PasskeyRegisterBeginResponse(BaseModel):
    session_id: str
    options: dict  # type: ignore[type-arg]


class PasskeyRegisterCompleteRequest(BaseModel):
    session_id: str
    credential: dict  # type: ignore[type-arg]
    name: str | None = None


class PasskeyLoginBeginResponse(BaseModel):
    session_id: str
    options: dict  # type: ignore[type-arg]


class PasskeyLoginCompleteRequest(BaseModel):
    session_id: str
    credential: dict  # type: ignore[type-arg]
