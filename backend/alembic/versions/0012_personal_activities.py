"""Persist user-entered itinerary activities separately from catalog facts."""
from alembic import op
import sqlalchemy as sa

revision = '0012_personal_activities'
down_revision = '0011_phase3'
branch_labels = depends_on = None


def upgrade():
    op.add_column('itinerary_items', sa.Column('personal_name', sa.String(120)))
    op.alter_column('itinerary_items', 'venue_id', nullable=True)
    op.drop_constraint('ck_item_valid', 'itinerary_items', type_='check')
    op.create_check_constraint('ck_item_valid', 'itinerary_items',
        'day_index >= 0 AND ends_at > starts_at AND position_version > 0 AND price_snapshot_minor >= 0')
    op.create_check_constraint(
        'ck_itinerary_item_source', 'itinerary_items',
        '(venue_id IS NULL) <> (personal_name IS NULL)',
    )


def downgrade():
    # PostgreSQL rejects this downgrade if personal activities still exist.
    op.alter_column('itinerary_items', 'venue_id', nullable=False)
    op.drop_constraint('ck_itinerary_item_source', 'itinerary_items', type_='check')
    op.drop_constraint('ck_item_valid', 'itinerary_items', type_='check')
    op.create_check_constraint('ck_item_valid', 'itinerary_items',
        'day_index >= 0 AND ends_at > starts_at AND position_version > 0 AND price_snapshot_minor > 0')
    op.drop_column('itinerary_items', 'personal_name')
