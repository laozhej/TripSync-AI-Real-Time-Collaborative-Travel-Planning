"""Retain used refresh hashes for reuse detection.

Revision ID: 0004_refresh_history
Revises: 0003_rooms
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_refresh_history"
down_revision = "0003_rooms"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "refresh_tokens",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("session_id", sa.Uuid(), sa.ForeignKey("auth_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_refresh_tokens_session", "refresh_tokens", ["session_id"])


def downgrade():
    op.drop_table("refresh_tokens")
