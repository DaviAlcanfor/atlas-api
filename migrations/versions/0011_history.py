"""country_history + history_periods (spec 016 stage 1: condensed "História de X" from pt.wikipedia)

Revision ID: 0011
Revises: 0010
"""
import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "country_history",
        sa.Column("iso2", sa.CHAR(length=2), sa.ForeignKey("polities.iso2"), primary_key=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("article_title", sa.Text(), nullable=False),
        sa.Column("article_url", sa.Text(), nullable=False),
        sa.Column("revision", sa.BigInteger(), nullable=True),
        sa.Column("retrieved_at", sa.Text(), nullable=True),
    )
    op.create_table(
        "history_periods",
        sa.Column("iso2", sa.CHAR(length=2), sa.ForeignKey("country_history.iso2"), primary_key=True),
        sa.Column("ord", sa.Integer(), primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("year_start", sa.Integer(), nullable=True),
        sa.Column("year_end", sa.Integer(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("history_periods")
    op.drop_table("country_history")
