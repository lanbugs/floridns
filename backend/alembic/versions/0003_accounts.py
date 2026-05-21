"""add accounts tables

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-17
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

# Reuse the enum that was created in migration 0001 — do not re-create it.
_userrole = PgEnum("superadmin", "admin", "operator", "viewer", name="userrole", create_type=False)


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(128), unique=True, nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "account_zones",
        sa.Column("account_id", UUID(as_uuid=True), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("zone_name", sa.String(255), nullable=False),
        sa.PrimaryKeyConstraint("account_id", "zone_name"),
    )

    op.create_table(
        "account_users",
        sa.Column("account_id", UUID(as_uuid=True), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", _userrole, nullable=False),
        sa.PrimaryKeyConstraint("account_id", "user_id"),
    )


def downgrade() -> None:
    op.drop_table("account_users")
    op.drop_table("account_zones")
    op.drop_table("accounts")
