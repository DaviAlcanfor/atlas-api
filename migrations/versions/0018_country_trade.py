"""country_trade (spec 029 phase 2): BACI exports, imports, top products and partners per country; additive

Revision ID: 0018
Revises: 0017
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "country_trade",
        sa.Column("iso2", sa.CHAR(length=2), sa.ForeignKey("polities.iso2"), primary_key=True),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("exports_usd", sa.Float(), nullable=False),
        sa.Column("imports_usd", sa.Float(), nullable=False),
        sa.Column("top_exports", JSONB(), nullable=False),
        sa.Column("top_destinations", JSONB(), nullable=False),
        sa.Column("top_origins", JSONB(), nullable=False),
        sa.Column("source_ids", JSONB(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("country_trade")
