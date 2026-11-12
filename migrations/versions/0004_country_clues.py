"""country_facts clue columns (spec 003)

Revision ID: 0004
Revises: 0003
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for col in ("driving_side", "calling_code", "tld", "plate_code"):
        op.add_column("country_facts", sa.Column(col, sa.Text(), nullable=True))
    op.add_column("country_facts",
                  sa.Column("scripts", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.create_check_constraint("ck_country_facts_driving_side", "country_facts",
                               "driving_side IS NULL OR driving_side IN ('left', 'right')")


def downgrade() -> None:
    op.drop_constraint("ck_country_facts_driving_side", "country_facts", type_="check")
    for col in ("scripts", "plate_code", "tld", "calling_code", "driving_side"):
        op.drop_column("country_facts", col)
