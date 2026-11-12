"""capitals (spec 019: several capitals per country)

Revision ID: 0007
Revises: 0006
"""
import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "capitals",
        sa.Column("iso2", sa.CHAR(length=2), nullable=False),
        sa.Column("ord", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lng", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["iso2"], ["polities.iso2"]),
        sa.PrimaryKeyConstraint("iso2", "ord"),
    )


def downgrade() -> None:
    op.drop_table("capitals")
