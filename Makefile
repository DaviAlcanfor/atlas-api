dev:
	uv run uvicorn atlas_api.main:app --reload --app-dir src
test:
	uv run pytest
lint:
	uv run ruff check .
typecheck:
	uv run mypy
openapi:
	uv run python scripts/export_openapi.py
etl-wikidata:
	uv run --group etl python -m etl wikidata
etl-worldbank:
	uv run --group etl python -m etl worldbank
etl-restcountries:
	uv run python -m etl restcountries
# Phase 1+: migrate, seed, import, import-facts, etl-modern-geometry, etl-snapshots, sync-geometry
db-up:
	docker compose up -d --wait
migrate:
	uv run alembic upgrade head
