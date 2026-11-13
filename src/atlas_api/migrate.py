"""Schema migrations at startup (2026-11-12): API PRs were merged three times before the production DB was migrated, and every
new table answered 503 until someone ran Alembic by hand. Now each deploy brings the schema to `head` before serving.

Only the SCHEMA: data still comes from `atlas_api.cli import-content` / `import-facts` (data_out/ is not deployed).
A Postgres advisory lock serializes replicas starting together; the second one finds the schema at head and does nothing.
Migrations must stay additive (new tables/columns) so the previous release keeps working while the new one starts.
"""
import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, text

LOCK_ID = 727_100_001  # arbitrary, constant: same key in every replica
MIGRATIONS = Path(__file__).resolve().parents[2] / "migrations"

log = logging.getLogger(__name__)


def upgrade_to_head(engine: Engine) -> None:
    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS))
    with engine.connect() as conn:
        conn.execute(text("SELECT pg_advisory_lock(:k)"), {"k": LOCK_ID})
        try:
            cfg.attributes["connection"] = conn  # migrations/env.py reuses it (and commits)
            command.upgrade(cfg, "head")
        finally:
            conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": LOCK_ID})
            conn.commit()
    log.info("schema at head")
