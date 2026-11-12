"""country_languages (spec 017)

Revision ID: 0008
Revises: 0007
"""
import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "country_languages",
        sa.Column("iso2", sa.CHAR(length=2), nullable=False),
        sa.Column("qid", sa.Text(), nullable=False),
        sa.Column("ord", sa.Integer(), nullable=False),
        sa.Column("code", sa.Text(), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("where", sa.Text(), nullable=True),
        sa.Column("speakers", sa.BigInteger(), nullable=True),
        sa.Column("speakers_year", sa.Integer(), nullable=True),
        sa.Column("family", sa.Text(), nullable=True),
        sa.Column("endangerment", sa.Text(), nullable=True),
        sa.Column("wikipedia_url", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('official', 'co_official', 'sign', 'historical', 'indigenous', 'immigrant')",
            name="ck_country_languages_status",
        ),
        sa.ForeignKeyConstraint(["iso2"], ["polities.iso2"]),
        sa.PrimaryKeyConstraint("iso2", "qid"),
    )


def downgrade() -> None:
    op.drop_table("country_languages")
