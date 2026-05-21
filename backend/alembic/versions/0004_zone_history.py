"""add zone_history table

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-18
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON, UUID

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "zone_history",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("zone_name", sa.String(255), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("snapshot_before", JSON, nullable=False),
        sa.Column("snapshot_after", JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_zone_history_zone_name", "zone_history", ["zone_name"])
    op.create_index("ix_zone_history_created_at", "zone_history", ["created_at"])


def downgrade() -> None:
    op.drop_table("zone_history")
