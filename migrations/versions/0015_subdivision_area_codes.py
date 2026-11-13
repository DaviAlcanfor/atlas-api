"""subdivisions.area_codes (spec 026): telephone area codes (DDD) of each admin-1 unit; additive

Revision ID: 0015
Revises: 0014
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("subdivisions", sa.Column("area_codes", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("subdivisions", "area_codes")
