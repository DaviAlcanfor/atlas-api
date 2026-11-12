"""fx_rates, currency_stats (spec 009)

Revision ID: 0010
Revises: 0009
"""
import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fx_rates",
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("code", sa.CHAR(length=3), nullable=False),
        sa.Column("rate", sa.Float(), nullable=False),
        sa.Column("source_id", sa.Text(), sa.ForeignKey("sources.id"), nullable=False),
        sa.PrimaryKeyConstraint("code", "date"),
    )
    op.create_index("ix_fx_rates_date", "fx_rates", ["date"])
    op.create_table(
        "currency_stats",
        sa.Column("code", sa.CHAR(length=3), primary_key=True),
        sa.Column("vs", sa.CHAR(length=3), nullable=False),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("change_1y", sa.Float(), nullable=True),
        sa.Column("change_5y", sa.Float(), nullable=True),
        sa.Column("volatility_1y", sa.Float(), nullable=True),
        sa.Column("max_drawdown_1y", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("currency_stats")
    op.drop_table("fx_rates")
