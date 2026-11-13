"""subdivisions (spec 024): facts + flag of each admin-1 unit drawn by the web, keyed by Wikidata id

Revision ID: 0012
Revises: 0011
"""
import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "subdivisions",
        sa.Column("wikidata_id", sa.Text(), primary_key=True),
        sa.Column("iso2", sa.CHAR(length=2), sa.ForeignKey("polities.iso2"), nullable=False, index=True),
        sa.Column("ord", sa.Integer(), nullable=False),
        sa.Column("code", sa.Text(), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("capital", sa.Text(), nullable=True),
        sa.Column("area_km2", sa.Float(), nullable=True),
        sa.Column("population", sa.BigInteger(), nullable=True),
        sa.Column("population_year", sa.Integer(), nullable=True),
        sa.Column("flag_url", sa.Text(), nullable=True),
        sa.Column("flag_credit", sa.Text(), nullable=True),
        sa.Column("flag_license", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("subdivisions")
