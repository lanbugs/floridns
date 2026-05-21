"""refresh_token_denylist table

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-21

"""
from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "refresh_token_denylist",
        sa.Column("jti", sa.String(64), primary_key=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_refresh_token_denylist_expires_at", "refresh_token_denylist", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_refresh_token_denylist_expires_at", "refresh_token_denylist")
    op.drop_table("refresh_token_denylist")
