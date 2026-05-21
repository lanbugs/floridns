import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class DynDnsHost(Base, TimestampMixin):
    __tablename__ = "dyndns_hosts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    hostname: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    zone_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    last_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    last_ip6: Mapped[str | None] = mapped_column(String(45), nullable=True)
    last_update: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
    offline: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    user: Mapped["User"] = relationship("User", back_populates="dyndns_hosts")  # type: ignore[name-defined]
