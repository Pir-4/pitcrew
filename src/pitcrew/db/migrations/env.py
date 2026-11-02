"""Alembic environment.

The service passes its own connection through `config.attributes` (see `pitcrew.db.migrate.migrate`);
the `alembic` CLI (`alembic.ini` at the repo root) connects to `DATABASE_URL` from the settings.
"""

from alembic import context
from sqlalchemy import Connection, create_engine

from pitcrew.config.settings import get_settings

# The package, not models.base: importing it registers every table in Base.metadata.
from pitcrew.db.models import Base


def _run(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()


connection = context.config.attributes.get("connection")
if connection is not None:
    _run(connection)
else:
    engine = create_engine(str(get_settings().database_url))
    with engine.begin() as cli_connection:
        _run(cli_connection)
    engine.dispose()
