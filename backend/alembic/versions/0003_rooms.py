"""Trip membership, invitations, board items and durable event records.

Revision ID: 0003_rooms
Revises: 0002_datasets
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_rooms"
down_revision = "0002_datasets"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "trips",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("leader_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), sa.ForeignKey("datasets.id"), nullable=False),
        sa.Column("destination", sa.String(200), nullable=False),
        sa.Column("timezone", sa.String(100), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("total_budget_minor", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="drafting"),
        sa.Column("room_locked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("max_participants", sa.Integer(), nullable=False),
        sa.Column("room_seq", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("committed_seq", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("room_epoch", sa.Uuid(), nullable=False),
        sa.Column("state_version", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("end_date >= start_date", name="ck_trip_dates"),
        sa.CheckConstraint("total_budget_minor > 0", name="ck_trip_budget"),
        sa.CheckConstraint("max_participants BETWEEN 2 AND 50", name="ck_trip_capacity"),
        sa.CheckConstraint("room_seq >= 0 AND committed_seq >= 0 AND committed_seq <= room_seq AND state_version >= 0", name="ck_trip_sequences"),
        sa.CheckConstraint("status IN ('drafting','live','finalized')", name="ck_trip_status"),
    )
    op.create_table(
        "memberships",
        sa.Column("trip_id", sa.Uuid(), sa.ForeignKey("trips.id"), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("role", sa.String(10), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="active"),
        sa.Column("can_pin", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("muted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("role IN ('viewer','planner','leader')", name="ck_membership_role"),
        sa.CheckConstraint("status IN ('active','left','removed')", name="ck_membership_status"),
    )
    op.create_index("uq_active_trip_leader", "memberships", ["trip_id"], unique=True,
                    postgresql_where=sa.text("role = 'leader' AND status = 'active'"))
    op.create_index("ix_memberships_user_status", "memberships", ["user_id", "status"])
    op.create_table(
        "invites",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("trip_id", sa.Uuid(), sa.ForeignKey("trips.id"), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("assigned_role", sa.String(10), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("max_uses", sa.Integer(), nullable=False),
        sa.Column("uses", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("assigned_role IN ('viewer','planner')", name="ck_invite_role"),
        sa.CheckConstraint("max_uses > 0 AND uses >= 0 AND uses <= max_uses", name="ck_invite_uses"),
    )
    op.create_table(
        "itinerary_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("trip_id", sa.Uuid(), sa.ForeignKey("trips.id"), nullable=False),
        sa.Column("venue_id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("day_index", sa.Integer(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lifecycle_stage", sa.String(10), nullable=False),
        sa.Column("pinned_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("position_version", sa.BigInteger(), nullable=False),
        sa.Column("removed_at", sa.DateTime(timezone=True)),
        sa.Column("price_snapshot_minor", sa.BigInteger(), nullable=False),
        sa.Column("split_mode", sa.String(10), nullable=False),
        sa.ForeignKeyConstraint(["venue_id", "dataset_id"], ["venue_metadata.id", "venue_metadata.dataset_id"]),
        sa.CheckConstraint("day_index >= 0 AND ends_at > starts_at AND position_version > 0 AND price_snapshot_minor > 0", name="ck_item_valid"),
        sa.CheckConstraint("lifecycle_stage IN ('drafting','voting','locked')", name="ck_item_stage"),
        sa.CheckConstraint("split_mode IN ('even','weighted')", name="ck_item_split"),
    )
    op.create_index("ix_items_trip_day_start", "itinerary_items", ["trip_id", "day_index", "starts_at"])
    op.create_table(
        "item_attendees",
        sa.Column("item_id", sa.Uuid(), sa.ForeignKey("itinerary_items.id"), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("weight", sa.Integer(), nullable=False),
        sa.CheckConstraint("weight >= 0", name="ck_attendee_weight"),
    )
    op.create_table(
        "room_events",
        sa.Column("trip_id", sa.Uuid(), sa.ForeignKey("trips.id"), primary_key=True),
        sa.Column("room_seq", sa.BigInteger(), primary_key=True),
        sa.Column("event_id", sa.Uuid(), nullable=False, unique=True),
        sa.Column("command_id", sa.Uuid()),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("type", sa.String(80), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("trip_id", "command_id"),
    )
    op.create_table(
        "room_snapshots",
        sa.Column("trip_id", sa.Uuid(), sa.ForeignKey("trips.id"), primary_key=True),
        sa.Column("committed_seq", sa.BigInteger(), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("state", postgresql.JSONB(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade():
    for table in ("room_snapshots", "room_events", "item_attendees", "itinerary_items", "invites", "memberships", "trips"):
        op.drop_table(table)
