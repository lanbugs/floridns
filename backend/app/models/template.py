import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class ZoneTemplate(Base, TimestampMixin):
    __tablename__ = "zone_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    records: Mapped[list["ZoneTemplateRecord"]] = relationship(
        "ZoneTemplateRecord", back_populates="template", cascade="all, delete-orphan",
        order_by="ZoneTemplateRecord.name", lazy="selectin"
    )


class ZoneTemplateRecord(Base):
    __tablename__ = "zone_template_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("zone_templates.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    ttl: Mapped[int] = mapped_column(Integer, nullable=False, default=3600)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    template: Mapped["ZoneTemplate"] = relationship("ZoneTemplate", back_populates="records")
