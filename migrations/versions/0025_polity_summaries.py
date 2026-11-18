"""polity_summaries (spec 042): Wikipedia summary per historical entity (key = Wikidata Q-id); additive

Revision ID: 0025
Revises: 0024
"""
import sqlalchemy as sa
from alembic import op

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "polity_summaries",
        sa.Column("wikidata_qid", sa.Text(), primary_key=True),
        sa.Column("lang", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("extract", sa.Text(), nullable=False),
        sa.Column("page_url", sa.Text(), nullable=False),
        sa.Column("license", sa.Text(), nullable=False),
        sa.Column("revision", sa.BigInteger(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("thumbnail_url", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("polity_summaries")
