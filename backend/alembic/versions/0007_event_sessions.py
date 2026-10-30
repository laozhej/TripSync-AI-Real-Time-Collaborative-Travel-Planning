"""Correct the planning-session reference of existing first-slice events.

Revision ID: 0007_event_sessions
Revises: 0006_planning_session
"""
from alembic import op
import sqlalchemy as sa
revision = '0007_event_sessions'
down_revision = '0006_planning_session'
branch_labels = None
depends_on = None


def upgrade():
    # Preserve the old identity so the correction can be reversed without loss.
    op.add_column('room_events', sa.Column('legacy_auth_session_id', sa.Uuid(), nullable=True))
    op.execute("""UPDATE room_events AS e SET legacy_auth_session_id=e.session_id, session_id=t.planning_session_id
        FROM trips AS t WHERE e.trip_id=t.id AND e.type='trip.board.update'""")


def downgrade():
    op.execute("UPDATE room_events SET session_id=legacy_auth_session_id WHERE legacy_auth_session_id IS NOT NULL")
    op.drop_column('room_events', 'legacy_auth_session_id')
