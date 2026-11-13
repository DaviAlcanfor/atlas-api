"""ideologies (spec 018): glossary kind "ideology" + figures, people and parties per current

Revision ID: 0014
Revises: 0013
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None

OLD = "kind IN ('regime', 'system', 'region', 'membership', 'currency', 'other')"
NEW = "kind IN ('regime', 'system', 'region', 'membership', 'currency', 'ideology', 'other')"


def upgrade() -> None:
    op.drop_constraint("ck_glossary_terms_kind", "glossary_terms", type_="check")
    op.create_check_constraint("ck_glossary_terms_kind", "glossary_terms", NEW)
    op.create_table(
        "ideology_people",
        sa.Column("person_id", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("birth_year", sa.Integer(), nullable=True),
        sa.Column("death_year", sa.Integer(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("works", postgresql.JSONB(), nullable=False),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("image_credit", sa.Text(), nullable=True),
        sa.Column("image_license", sa.Text(), nullable=True),
        sa.Column("wikipedia_url", sa.Text(), nullable=True),
        sa.CheckConstraint("role IN ('thinker', 'leader', 'activist', 'other')", name="ck_ideology_people_role"),
    )
    op.create_table(  # scope = ISO2 of the country, or 'WORLD' for the current's page ("most known" worldwide)
        "ideology_figures",
        sa.Column("ideology_id", sa.Text(), sa.ForeignKey("glossary_terms.id"), primary_key=True),
        sa.Column("scope", sa.Text(), primary_key=True),
        sa.Column("person_id", sa.Text(), sa.ForeignKey("ideology_people.person_id"), primary_key=True),
        sa.Column("ord", sa.Integer(), nullable=False),
        sa.Column("via", sa.Text(), nullable=False),
        sa.Column("party_id", sa.Text(), nullable=True),
        sa.Column("party_name", sa.Text(), nullable=True),
        sa.CheckConstraint("via IN ('declared', 'party')", name="ck_ideology_figures_via"),
    )
    op.create_table(
        "ideology_parties",
        sa.Column("ideology_id", sa.Text(), sa.ForeignKey("glossary_terms.id"), primary_key=True),
        sa.Column("iso2", sa.CHAR(length=2), sa.ForeignKey("polities.iso2"), primary_key=True),
        sa.Column("party_id", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("ord", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("ideology_parties")
    op.drop_table("ideology_figures")
    op.drop_table("ideology_people")
    op.drop_constraint("ck_glossary_terms_kind", "glossary_terms", type_="check")
    op.create_check_constraint("ck_glossary_terms_kind", "glossary_terms", OLD)
