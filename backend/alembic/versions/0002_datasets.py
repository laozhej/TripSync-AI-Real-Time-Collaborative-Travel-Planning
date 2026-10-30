"""Dataset versions and authored metadata.

Revision ID: 0002_datasets
Revises: 0001_identity
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_datasets"
down_revision = "0001_identity"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "datasets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("destination", sa.String(200), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("timezone", sa.String(100), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("provenance", postgresql.JSONB(), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("version > 0", name="ck_dataset_version"),
        sa.CheckConstraint("status IN ('staging', 'active', 'retired')", name="ck_dataset_status"),
        sa.UniqueConstraint("destination", "version"),
        sa.UniqueConstraint("destination", "checksum"),
    )
    op.create_index("uq_active_dataset_destination", "datasets", ["destination"], unique=True,
                    postgresql_where=sa.text("status = 'active'"))
    op.create_table(
        "venue_metadata",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), sa.ForeignKey("datasets.id"), nullable=False),
        sa.Column("source_id", sa.String(80), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("price_per_person_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("latitude", sa.Numeric(10, 7), nullable=False),
        sa.Column("longitude", sa.Numeric(10, 7), nullable=False),
        sa.Column("rating", sa.Numeric(3, 2)),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("hours", postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("id", "dataset_id"),
        sa.UniqueConstraint("dataset_id", "source_id"),
        sa.CheckConstraint("price_per_person_minor > 0", name="ck_venue_price"),
        sa.CheckConstraint("latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180", name="ck_venue_coordinates"),
        sa.CheckConstraint("rating IS NULL OR rating BETWEEN 0 AND 5", name="ck_venue_rating"),
    )
    op.create_index("ix_venues_dataset_coordinates", "venue_metadata", ["dataset_id", "latitude", "longitude"])
    op.create_table(
        "venue_dietary_tags",
        sa.Column("venue_id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("tag", sa.String(40), nullable=False),
        sa.PrimaryKeyConstraint("venue_id", "dataset_id", "tag"),
        sa.ForeignKeyConstraint(["venue_id", "dataset_id"], ["venue_metadata.id", "venue_metadata.dataset_id"]),
    )
    op.create_table(
        "transit_metadata",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("dataset_id", sa.Uuid(), sa.ForeignKey("datasets.id"), nullable=False),
        sa.Column("source_id", sa.String(80), nullable=False),
        sa.Column("data", postgresql.JSONB(), nullable=False),
        sa.UniqueConstraint("dataset_id", "source_id"),
    )
    op.create_table(
        "weather_metadata",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("dataset_id", sa.Uuid(), sa.ForeignKey("datasets.id"), nullable=False),
        sa.Column("source_id", sa.String(80), nullable=False),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("data", postgresql.JSONB(), nullable=False),
        sa.UniqueConstraint("dataset_id", "source_id"),
        sa.UniqueConstraint("dataset_id", "local_date"),
    )


def downgrade():
    op.drop_table("weather_metadata")
    op.drop_table("transit_metadata")
    op.drop_table("venue_dietary_tags")
    op.drop_table("venue_metadata")
    op.drop_table("datasets")
