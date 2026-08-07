"""Database configuration, kept importable without the rest of the settings.

Alembic and the provisioning CLI need somewhere to find the database and nothing
else. This section lives in its own module -- a sibling of
:mod:`misbot_auth_server.settings`, never a submodule of it -- so importing it
does not construct :class:`~misbot_auth_server.settings.Settings` and therefore
does not demand the JWT signing key. Migrating a table should not require the
key the server signs tokens with.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(
        # Mirrors the root settings, so a standalone read and a read through
        # `Settings.database` resolve to the same values.
        env_file=(".env.dev", ".env"),
        env_prefix="MISBOT_AUTH_DATABASE__",
        extra="ignore",
    )

    sql_echo: bool = Field(default=False, description="SQLAlchemy verbose query log mode")
    db_file: Path = Field(
        default=Path("db/authdb.sqlite"),
        description="SQLite database file; relative paths resolve against the working directory",
    )

    @property
    def sqlite_connection_string(self) -> str:
        return f"sqlite+aiosqlite:///{self.db_file.as_posix()}"


@lru_cache(maxsize=1)
def get_database_settings() -> DatabaseSettings:
    return DatabaseSettings()
