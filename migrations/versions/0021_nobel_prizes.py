"""nobel_prizes (spec 033): one row per (laureate, prize) from the Nobel Prize API; additive

Revision ID: 0021
Revises: 0020
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "nobel_prizes",
        sa.Column("laureate_id", sa.Text(), primary_key=True),
        sa.Column("year", sa.Integer(), primary_key=True),
        sa.Column("category", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("motivation", sa.Text(), nullable=True),
        sa.Column("portion", sa.Text(), nullable=True),
        sa.Column("origin_iso2", sa.CHAR(length=2), nullable=True),
        sa.Column("affiliations", JSONB(), nullable=False),
        sa.Column("wikipedia_url", sa.Text(), nullable=True),
        sa.Column("url", sa.Text(), nullable=False),
    )
    op.create_index("ix_nobel_prizes_origin_iso2", "nobel_prizes", ["origin_iso2"])


def downgrade() -> None:
    op.drop_table("nobel_prizes")
