import asyncio
from logging.config import fileConfig

from sqlalchemy.engine import Connection

from alembic import context
from misbot_auth_server.db.engine import engine
from misbot_auth_server.db.settings import get_database_settings
from misbot_auth_server.db.tables import metadata

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Model metadata for 'autogenerate' support. The database URL is not read from
# alembic.ini at all -- migrations run against the application's own engine, so
# there is exactly one place the database location is configured.
target_metadata = metadata


def run_migrations_offline() -> None:
    """Emit the migration SQL without connecting to a database."""
    context.configure(
        # Not `config.get_main_option("sqlalchemy.url")`: alembic.ini carries no
        # URL on purpose, so the application settings are the one source.
        url=get_database_settings().sqlite_connection_string,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # SQLite cannot ALTER most things in place; batch mode rebuilds the
        # table instead. Irrelevant to the initial revision, essential later.
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations against the application engine."""
    # SQLite will not create intermediate directories for its own file.
    get_database_settings().db_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        async with engine.connect() as connection:
            await connection.run_sync(do_run_migrations)
    finally:
        # Deliberately no `except Exception: log and continue`. Swallowing here
        # would let `upgrade head` exit 0 on a broken migration, and a container
        # entrypoint would then start against a half-migrated database.
        await engine.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
