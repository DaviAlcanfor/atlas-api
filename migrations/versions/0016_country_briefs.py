"""country_briefs (spec 022): the country summary built by etl ai-summaries (formula + optional AI rewording); additive

Revision ID: 0016
Revises: 0015
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "country_briefs",
        sa.Column("iso2", sa.CHAR(length=2), sa.ForeignKey("polities.iso2"), primary_key=True),
        sa.Column("tldr", sa.Text(), nullable=False),
        sa.Column("now", sa.Text(), nullable=True),
        sa.Column("method", sa.Text(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_ids", JSONB(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("country_briefs")
