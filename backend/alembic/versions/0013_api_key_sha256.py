"""api_key fast-lookup hash

Adds key_sha256 column to api_keys so lookups can bypass the O(n) bcrypt scan.
New keys get a SHA-256 hash on creation; legacy keys (bcrypt-only) keep working
via fallback until they are deleted or recreated.

Revision ID: 0013
Revises: 0012
Create Date: 2026-05-22

"""
import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "api_keys",
        sa.Column("key_sha256", sa.String(64), nullable=True),
    )
    op.create_unique_constraint("uq_api_keys_key_sha256", "api_keys", ["key_sha256"])
    op.create_index("ix_api_keys_key_sha256", "api_keys", ["key_sha256"])


def downgrade() -> None:
    op.drop_index("ix_api_keys_key_sha256", table_name="api_keys")
    op.drop_constraint("uq_api_keys_key_sha256", "api_keys", type_="unique")
    op.drop_column("api_keys", "key_sha256")
