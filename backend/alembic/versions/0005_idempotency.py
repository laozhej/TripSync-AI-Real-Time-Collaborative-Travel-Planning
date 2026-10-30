"""Persist idempotent HTTP mutation responses.

Revision ID: 0005_idempotency
Revises: 0004_refresh_history
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision = "0005_idempotency"
down_revision = "0004_refresh_history"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("http_idempotency",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("key", sa.Uuid(), primary_key=True),
        sa.Column("route", sa.String(100), nullable=False),
        sa.Column("body_hash", sa.String(64), nullable=False),
        sa.Column("response", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))


def downgrade():
    op.drop_table("http_idempotency")
