from contextlib import nullcontext
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

from atlas_api.config import get_settings
from atlas_api.db.models import Base

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_online() -> None:
    # Tests hand in an open connection to their own database; otherwise use DATABASE_URL.
    shared = config.attributes.get("connection")
    cm = nullcontext(shared) if shared is not None else create_engine(get_settings().database_url).connect()
    with cm as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
        connection.commit()


run_migrations_online()
