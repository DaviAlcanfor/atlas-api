# Atlas API: agent notes

Read-only API: modern countries, historical polities, timelines, snapshot-polygon -> polity mapping.
A separate agent builds the web front in ANOTHER repo (not visible here).

## Rules
- `contract/CONTRACT.md` is FROZEN. Never edit. Problems go in `contract/CHANGE_REQUESTS.md`, then stop and tell the user.
- Secrets only via env vars (`DATABASE_URL`, `RESTCOUNTRIES_API_KEY`, `CORS_ORIGINS`). Never a real `.env` in git.
- The API process (`src/atlas_api`) must NEVER import the `etl` dependency group.
- Only writer to the DB: `python -m atlas_api.cli import-content` (idempotent, one transaction). No write endpoints.
- ORM / bound parameters only. Never format SQL strings. Never invent data: missing = null.
- Work in phases (0-4); STOP after each for user review. Explain new concepts plainly (user is a data analyst, back-end beginner).

## Stack
Python 3.12+, uv, FastAPI, Pydantic v2, SQLAlchemy 2 (sync, psycopg 3), Alembic, Postgres (docker-compose local, Supabase prod), pytest against real Postgres, ruff, mypy strict.

## Commands (Makefile; on Windows without make, run the underlying `uv run ...` line)
dev, test, lint, typecheck, openapi (writes `openapi.generated.json`). Later: migrate, seed, import, etl-*, sync-geometry.

## Data model rules
- No year 0 (1 BCE = -1). Polity exists in Y iff start <= Y and (end is null or Y <= end), inclusive.
- Name as of Y: covering `polity_names` row, else `polities.name`. Nearest snapshot: ties -> earlier, return `distance_years`.
- Timelines sorted by (year_start, id). Succession acyclic. `has_content` = summary or >=1 event.

## Layout
src/atlas_api/: main.py (app factory + lifespan), config.py (pydantic-settings), deps.py (DI), errors.py (exceptions -> problem+json), schemas/ (contract models), routers/ (one per resource), fixtures/ (Phase 0 JSON stubs in data/, replaced by DB in Phase 1).
etl/: settings.py, cli.py, restcountries/{models,client,transform,pipeline}.py. Run: `uv run python -m etl restcountries` (reads .env itself).
docs/CONTRACT_NOTES.md maps contract -> code (the contract itself is frozen).

## Status
Phase 0 done: routes return stub fixtures (`fixtures.py`, not authoritative). ETL `restcountries` written (list endpoint, 3-day cache, Free plan 1000 req/mo). Next: Phase 1 (DB, importer, real endpoints).
