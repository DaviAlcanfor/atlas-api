"""leaders (spec 006, v1.1)

Revision ID: 0005
Revises: 0004
"""
import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "leaders",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("iso2", sa.CHAR(length=2), nullable=False),
        sa.Column("person_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("office", sa.Text(), nullable=True),
        sa.Column("start", sa.Text(), nullable=True),
        sa.Column("end", sa.Text(), nullable=True),
        sa.Column("party_id", sa.Text(), nullable=True),
        sa.Column("party_name", sa.Text(), nullable=True),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("image_credit", sa.Text(), nullable=True),
        sa.Column("image_license", sa.Text(), nullable=True),
        sa.Column("wikipedia_url", sa.Text(), nullable=True),
        sa.CheckConstraint("role IN ('head_of_state', 'head_of_government')", name="ck_leaders_role"),
        sa.ForeignKeyConstraint(["iso2"], ["polities.iso2"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_leaders_iso2", "leaders", ["iso2"])


def downgrade() -> None:
    op.drop_index("ix_leaders_iso2", table_name="leaders")
    op.drop_table("leaders")
