"""history_events (spec 016 stage 2): notable dated events per country from Wikidata (not human-reviewed)

Revision ID: 0013
Revises: 0012
"""
import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "history_events",
        sa.Column("iso2", sa.CHAR(length=2), sa.ForeignKey("polities.iso2"), primary_key=True),
        sa.Column("qid", sa.Text(), primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("year_start", sa.Integer(), nullable=False),
        sa.Column("year_end", sa.Integer(), nullable=True),
        sa.Column("wikipedia_url", sa.Text(), nullable=True),
        sa.CheckConstraint("year_start <> 0 AND (year_end IS NULL OR year_end <> 0)", name="ck_history_events_no_year_zero"),
    )


def downgrade() -> None:
    op.drop_table("history_events")
