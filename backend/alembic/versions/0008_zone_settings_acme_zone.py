"""zone_settings table and api_key zone_restriction

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-18

"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("api_keys", sa.Column("zone_restriction", sa.String(255), nullable=True))

    op.create_table(
        "zone_settings",
        sa.Column("zone_name", sa.String(255), primary_key=True),
        sa.Column("auto_ptr", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("zone_settings")
    op.drop_column("api_keys", "zone_restriction")
