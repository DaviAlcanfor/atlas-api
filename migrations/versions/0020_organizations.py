"""organizations + organization_members (spec 032): curated memberships with join/leave dates; additive

Revision ID: 0020
Revises: 0019
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.Text(), sa.ForeignKey("glossary_terms.id"), primary_key=True),
        sa.Column("wikidata_qid", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("sources", JSONB(), nullable=False),
    )
    op.create_table(
        "organization_members",
        sa.Column("org_id", sa.Text(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("iso2", sa.CHAR(length=2), primary_key=True),
        sa.Column("joined", sa.Text(), primary_key=True),  # ISO 8601 with the source's precision: YYYY, YYYY-MM or YYYY-MM-DD
        sa.Column("left", sa.Text(), nullable=True),
        sa.Column("suspended", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("note", sa.Text(), nullable=True),
    )
    op.create_index("ix_organization_members_iso2", "organization_members", ["iso2"])


def downgrade() -> None:
    op.drop_table("organization_members")
    op.drop_table("organizations")
