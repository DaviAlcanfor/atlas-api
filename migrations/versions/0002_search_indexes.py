"""search: unaccent + pg_trgm extensions and trigram indexes

Revision ID: 0002
Revises: 0001

Extensions are created in schema public (on Supabase they would otherwise default to the
`extensions` schema, which is not on the search_path of every connection).
f_unaccent wraps unaccent() as IMMUTABLE, which Postgres requires to use it in an index.
Queries must use the exact same expression: lower(f_unaccent(col)).
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent WITH SCHEMA public")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public")
    op.execute(
        "CREATE OR REPLACE FUNCTION public.f_unaccent(text) RETURNS text "
        "LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT "
        "AS $$ SELECT public.unaccent('public.unaccent'::regdictionary, $1) $$"
    )
    op.execute(
        "CREATE INDEX ix_polities_name_trgm ON polities "
        "USING gin (lower(public.f_unaccent(name)) public.gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX ix_polity_names_name_trgm ON polity_names "
        "USING gin (lower(public.f_unaccent(name)) public.gin_trgm_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_polity_names_name_trgm")
    op.execute("DROP INDEX IF EXISTS ix_polities_name_trgm")
    op.execute("DROP FUNCTION IF EXISTS public.f_unaccent(text)")
    # Extensions are left installed on purpose (other objects may use them).
