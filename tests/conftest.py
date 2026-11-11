"""Tests run against REAL Postgres, in throwaway databases (*_test), never the dev/prod one."""
import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from atlas_api.facts import import_facts
from atlas_api.importer import import_content
from atlas_api.main import create_app

TEST_URL = make_url(
    os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg://atlas:atlas@localhost:5432/atlas_test")
)


def _fresh_database(name: str) -> Engine:
    """Drop + create database `name` (localhost only) and migrate it to head."""
    url = TEST_URL.set(database=name)
    assert url.host in ("localhost", "127.0.0.1"), "test databases must be local"
    assert name.endswith("_test")
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        c.execute(text(f'CREATE DATABASE "{name}"'))
    admin.dispose()
    eng = create_engine(url)
    cfg = Config("alembic.ini")
    with eng.connect() as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "head")
    return eng


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    eng = _fresh_database(TEST_URL.database or "atlas_test")
    yield eng
    eng.dispose()


@pytest.fixture(scope="session")
def api_client() -> Iterator[TestClient]:
    """The real app against a throwaway DB loaded with the REAL content/ and data_out/ files."""
    eng = _fresh_database("atlas_api_test")
    with Session(eng) as s, s.begin():
        import_content(s, Path("content"))
        if Path("data_out/wikidata.json").exists():
            import_facts(s, Path("data_out/wikidata.json"))
    url = eng.url.render_as_string(hide_password=False)
    with TestClient(create_app(url)) as client:
        client.app.state.test_url = url  # type: ignore[attr-defined]
        yield client
    eng.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    """One transaction per test, rolled back at the end: tests never see each other's rows."""
    conn = engine.connect()
    tx = conn.begin()
    s = Session(conn, join_transaction_mode="create_savepoint")
    yield s
    s.close()
    tx.rollback()
    conn.close()
