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
etl/: settings.py, cli.py. `etl/restcountries/` is NOT USED FOR THE DATABASE; kept for reference only (its ToS bar retaining data beyond 3 days and aggregating it into a downstream product). Do not extend it, do not write `import-facts` for it.
Persistent facts come from Wikidata (CC0) and World Bank Indicators (Phase 2). Read each upstream's docs/licence BEFORE coding its ETL and quote what you read.
docs/CONTRACT_NOTES.md maps contract -> code (the contract itself is frozen).

## Status
Phase 0 done: routes return stub fixtures (not authoritative). Phase 1 done except decisions: the API now reads REAL data from Postgres (`queries.py`, fixtures removed), ETag/304/X-Data-Version live, 196 countries seeded (placeholder start_year 1946, see README), `import-content` + `import-facts`, 40 tests on real Postgres. Pending user decisions: Germany/Yugoslavia/name periods (the 8 historical ids exist only as unverified placeholders, no succession); contract v1.1 (`Indicator`) is still NOT in the repo, so migration 0003/`indicators` are not done; news needs contract change CR-001.
Geometry: the WEB repo owns MODERN geometry. This repo owns HISTORICAL snapshots only. Micro-state `marker` comes from `content/markers.yaml` (iso2 -> lat,lng).
