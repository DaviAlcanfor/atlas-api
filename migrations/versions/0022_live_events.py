"""live_events (spec 034): recent earthquakes (USGS) and natural events (NASA EONET), kept a few days; additive

Revision ID: 0022
Revises: 0021
"""
import sqlalchemy as sa
from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "live_events",
        sa.Column("id", sa.Text(), primary_key=True),  # "usgs:<id>" | "eonet:<id>"
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lng", sa.Float(), nullable=False),
        sa.Column("magnitude", sa.Float(), nullable=True),
        sa.Column("magnitude_unit", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("time", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_live_events_time", "live_events", ["time"])


def downgrade() -> None:
    op.drop_table("live_events")
