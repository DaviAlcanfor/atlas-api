"""subdivisions.hdi/hdi_year/head (spec 024 phase 2): subnational HDI (GDL) + current head (Wikipedia lists); additive

Revision ID: 0019
Revises: 0018
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("subdivisions", sa.Column("hdi", sa.Float(), nullable=True))
    op.add_column("subdivisions", sa.Column("hdi_year", sa.Integer(), nullable=True))
    op.add_column("subdivisions", sa.Column("head", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("subdivisions", "head")
    op.drop_column("subdivisions", "hdi_year")
    op.drop_column("subdivisions", "hdi")
