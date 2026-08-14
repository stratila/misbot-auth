"""The process-wide SQLAlchemy engine.

Built at import time, like the settings it reads. The engine opens no connection
until first use, so importing this module is cheap and does not create the
database file.
"""

from sqlalchemy.ext.asyncio import create_async_engine

from misbot_auth_server.db.settings import get_database_settings

_settings = get_database_settings()

engine = create_async_engine(
    url=_settings.sqlite_connection_string,
    # Python 3.12's sqlite3 driver honours PEP 249 transaction control when
    # `autocommit` is False, so SQLAlchemy's BEGIN/COMMIT are the real thing
    # rather than the driver's legacy implicit-transaction emulation. The
    # `isolation_level = None` connect hook the sibling misbot project uses is
    # inert once this is set -- verified against CPython 3.12.
    connect_args={"autocommit": False},
    echo=_settings.sql_echo,
)
