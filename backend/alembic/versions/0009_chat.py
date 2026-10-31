"""Durable room chat messages and reactions.

Revision ID: 0009_chat
Revises: 0008_venue_search
"""
from alembic import op
import sqlalchemy as sa

revision = '0009_chat'
down_revision = '0008_venue_search'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('chat_messages',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('trip_id', sa.Uuid(), sa.ForeignKey('trips.id'), nullable=False),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('room_seq', sa.BigInteger(), nullable=False),
        sa.CheckConstraint('char_length(body) BETWEEN 1 AND 2000', name='ck_chat_body_length'),
        sa.UniqueConstraint('trip_id', 'room_seq'))
    op.create_index('ix_chat_trip_sequence', 'chat_messages', ['trip_id', 'room_seq'])
    op.create_table('reactions',
        sa.Column('message_id', sa.Uuid(), sa.ForeignKey('chat_messages.id'), primary_key=True),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id'), primary_key=True),
        sa.Column('emoji', sa.String(16), primary_key=True))


def downgrade():
    op.drop_table('reactions')
    op.drop_index('ix_chat_trip_sequence', table_name='chat_messages')
    op.drop_table('chat_messages')
