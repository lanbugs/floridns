"""dyndns_hosts table

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-20

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dyndns_hosts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("hostname", sa.String(255), nullable=False, unique=True),
        sa.Column("zone_name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("token_hash", sa.String(255), nullable=False),
        sa.Column("last_ip", sa.String(45), nullable=True),
        sa.Column("last_ip6", sa.String(45), nullable=True),
        sa.Column("last_update", sa.DateTime(timezone=True), nullable=True),
        sa.Column("offline", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_dyndns_hosts_hostname", "dyndns_hosts", ["hostname"])


def downgrade() -> None:
    op.drop_index("ix_dyndns_hosts_hostname", "dyndns_hosts")
    op.drop_table("dyndns_hosts")
