"""people (spec 007)

Revision ID: 0006
Revises: 0005
"""
import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "people",
        sa.Column("iso2", sa.CHAR(length=2), nullable=False),
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("occupation", sa.Text(), nullable=True),
        sa.Column("domain", sa.Text(), nullable=True),
        sa.Column("birth_year", sa.Integer(), nullable=True),
        sa.Column("death_year", sa.Integer(), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("image_credit", sa.Text(), nullable=True),
        sa.Column("image_license", sa.Text(), nullable=True),
        sa.Column("wikipedia_url", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "domain IS NULL OR domain IN ('arts', 'business_law', 'exploration', 'humanities', "
            "'institutions', 'public_figure', 'science_technology', 'sports')",
            name="ck_people_domain",
        ),
        sa.CheckConstraint("birth_year IS NULL OR birth_year <> 0", name="ck_people_no_year_zero"),
        sa.ForeignKeyConstraint(["iso2"], ["polities.iso2"]),
        sa.PrimaryKeyConstraint("iso2", "id"),
    )


def downgrade() -> None:
    op.drop_table("people")
