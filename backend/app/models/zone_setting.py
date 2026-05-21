from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ZoneSetting(Base, TimestampMixin):
    __tablename__ = "zone_settings"

    zone_name: Mapped[str] = mapped_column(String(255), primary_key=True)
    auto_ptr: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
