"""indicators, indicator_defs/stats/latest, compositions (specs 009, 015)

Revision ID: 0009
Revises: 0008
"""
import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "indicator_defs",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("unit", sa.Text(), nullable=False),
        sa.Column("source_id", sa.Text(), sa.ForeignKey("sources.id"), nullable=False),
    )
    op.create_table(
        "indicators",
        sa.Column("iso2", sa.CHAR(length=2), sa.ForeignKey("polities.iso2"), nullable=False),
        sa.Column("id", sa.Text(), sa.ForeignKey("indicator_defs.id"), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("source_id", sa.Text(), sa.ForeignKey("sources.id"), nullable=False),
        sa.PrimaryKeyConstraint("iso2", "id", "year"),
    )
    op.create_index("ix_indicators_id", "indicators", ["id"])
    op.create_table(
        "indicator_stats",
        sa.Column("id", sa.Text(), sa.ForeignKey("indicator_defs.id"), primary_key=True),
        sa.Column("n", sa.Integer(), nullable=False),
        sa.Column("min", sa.Float(), nullable=False),
        sa.Column("median", sa.Float(), nullable=False),
        sa.Column("max", sa.Float(), nullable=False),
    )
    op.create_table(
        "indicator_latest",
        sa.Column("iso2", sa.CHAR(length=2), sa.ForeignKey("polities.iso2"), nullable=False),
        sa.Column("id", sa.Text(), sa.ForeignKey("indicator_defs.id"), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("region_avg", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("iso2", "id"),
    )
    op.create_table(
        "compositions",
        sa.Column("iso2", sa.CHAR(length=2), sa.ForeignKey("polities.iso2"), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("share", sa.Float(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.CheckConstraint("kind IN ('religion', 'ethnicity')", name="ck_compositions_kind"),
        sa.PrimaryKeyConstraint("iso2", "kind", "label"),
    )


def downgrade() -> None:
    for t in ("compositions", "indicator_latest", "indicator_stats", "indicators", "indicator_defs"):
        op.drop_table(t)
