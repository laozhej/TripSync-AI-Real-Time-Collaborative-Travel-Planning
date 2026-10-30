"""Add the local full-text venue retrieval index.

Revision ID: 0008_venue_search
Revises: 0007_event_sessions
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision = '0008_venue_search'
down_revision = '0007_event_sessions'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('venue_metadata', sa.Column('search_vector', postgresql.TSVECTOR(), sa.Computed(
        "to_tsvector('english'::regconfig, coalesce(name, '') || ' ' || coalesce(description, ''))", persisted=True)))
    op.create_index('ix_venue_search_vector', 'venue_metadata', ['search_vector'], postgresql_using='gin')


def downgrade():
    op.drop_index('ix_venue_search_vector', table_name='venue_metadata')
    op.drop_column('venue_metadata', 'search_vector')
