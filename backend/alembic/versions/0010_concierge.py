"""Persisted category ceilings, attendee diets and idempotent Concierge responses.

Revision ID: 0010_concierge
Revises: 0009_chat
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision='0010_concierge'
down_revision='0009_chat'
branch_labels=None
depends_on=None


def upgrade():
    op.add_column('trips',sa.Column('category_ceilings',postgresql.JSONB(),nullable=False,server_default=sa.text("'{}'::jsonb")))
    op.add_column('memberships',sa.Column('constraints',postgresql.JSONB(),nullable=False,server_default=sa.text("'{}'::jsonb")))
    op.create_table('ai_questions',
        sa.Column('id',sa.Uuid(),primary_key=True),
        sa.Column('trip_id',sa.Uuid(),sa.ForeignKey('trips.id'),nullable=False),
        sa.Column('user_id',sa.Uuid(),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('request_key',sa.Uuid(),nullable=False),
        sa.Column('command_hash',sa.String(64),nullable=False),
        sa.Column('response',postgresql.JSONB(),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.UniqueConstraint('trip_id','user_id','request_key'))
    op.create_index('ix_ai_questions_trip_created','ai_questions',['trip_id','created_at'])


def downgrade():
    op.drop_index('ix_ai_questions_trip_created',table_name='ai_questions')
    op.drop_table('ai_questions')
    op.drop_column('memberships','constraints')
    op.drop_column('trips','category_ceilings')
