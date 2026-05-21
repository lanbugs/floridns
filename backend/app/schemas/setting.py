from typing import Any

from pydantic import BaseModel


class SettingUpsert(BaseModel):
    value: Any


class SlaveServer(BaseModel):
    name: str
    url: str
    api_key: str
    ssl_verify: bool = True


class SettingsResponse(BaseModel):
    """All settings as a key→value dict (values already JSON-decoded)."""

    settings: dict[str, Any]
