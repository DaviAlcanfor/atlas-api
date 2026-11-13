"""Startup migrations (migrate.py): idempotent, leaves the DB at Alembic head."""
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, text

from atlas_api.migrate import MIGRATIONS, upgrade_to_head


def test_upgrade_to_head_is_idempotent(engine: Engine) -> None:
    upgrade_to_head(engine)
    upgrade_to_head(engine)  # second replica: nothing to do, lock released
    head = ScriptDirectory(str(MIGRATIONS)).get_current_head()
    with engine.connect() as c:
        assert c.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == head
