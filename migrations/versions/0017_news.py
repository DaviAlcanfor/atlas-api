"""news (spec 008): geopolitical headlines from GDELT, classified by GPT-6 Luna decisions; additive

Revision ID: 0017
Revises: 0016
"""
import sqlalchemy as sa
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "news_items",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("url", sa.Text(), nullable=False, unique=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("outlet", sa.Text(), nullable=False),
        sa.Column("language", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("event_type", sa.Text(), nullable=False, index=True),
        sa.Column("geopolitical_p", sa.Float(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "news_item_countries",
        sa.Column("item_id", sa.Text(), sa.ForeignKey("news_items.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("iso2", sa.CHAR(length=2), primary_key=True),
        sa.Column("about_p", sa.Float(), nullable=False),
    )
    op.create_index("ix_news_item_countries_iso2", "news_item_countries", ["iso2"])


def downgrade() -> None:
    op.drop_table("news_item_countries")
    op.drop_table("news_items")
