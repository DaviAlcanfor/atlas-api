"""country_tech_trade (spec 041): BACI trade of tech HS4 headings per country (JSONB products); additive

Revision ID: 0024
Revises: 0023
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "country_tech_trade",
        sa.Column("iso2", sa.CHAR(length=2), sa.ForeignKey("polities.iso2"), primary_key=True),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("products", JSONB(), nullable=False),
        sa.Column("source_ids", JSONB(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("country_tech_trade")
