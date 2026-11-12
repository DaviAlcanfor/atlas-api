"""glossary_terms + country_facts.regime_id / regime (spec 004)

Revision ID: 0003
Revises: 0002
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "glossary_terms",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("short", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("icon", sa.Text(), nullable=True),
        sa.Column("sources", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.CheckConstraint(
            "kind IN ('regime', 'system', 'region', 'membership', 'currency', 'other')",
            name="ck_glossary_terms_kind",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.add_column("country_facts", sa.Column("regime_id", sa.Text(), nullable=True))
    op.add_column("country_facts", sa.Column("regime", sa.Text(), nullable=True))
    op.create_foreign_key("fk_country_facts_regime_id", "country_facts", "glossary_terms",
                          ["regime_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint("fk_country_facts_regime_id", "country_facts", type_="foreignkey")
    op.drop_column("country_facts", "regime")
    op.drop_column("country_facts", "regime_id")
    op.drop_table("glossary_terms")
