"""Stable planning-session identity on each trip.

Revision ID: 0006_planning_session
Revises: 0005_idempotency
"""
from alembic import op
import sqlalchemy as sa

revision = '0006_planning_session'
down_revision = '0005_idempotency'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('trips', sa.Column('planning_session_id', sa.Uuid(), nullable=False,
                                     server_default=sa.text('gen_random_uuid()')))


def downgrade():
    op.drop_column('trips', 'planning_session_id')
