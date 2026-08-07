import os
import subprocess
import sys
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

from misbot_auth_server.db import clients as clients_db
from misbot_auth_server.db.tables import clients
from misbot_auth_server.models.clients import Client

PROJECT_ROOT = Path(__file__).parents[2]


@pytest.fixture(scope="session")
def migrated_db(tmp_path_factory):
    """A database built by running the real migrations, not metadata.create_all.

    Going through Alembic is what makes model/migration drift visible; building
    the schema from the metadata would pass even if a migration were missing.
    """
    db_file = tmp_path_factory.mktemp("db") / "authdb.sqlite"
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
        cwd=PROJECT_ROOT,
        env={**os.environ, "MISBOT_AUTH_DATABASE__DB_FILE": str(db_file)},
        check=True,
        capture_output=True,
    )
    return db_file


@pytest_asyncio.fixture
async def db(migrated_db, monkeypatch):
    """An engine on the migrated database, emptied between tests."""
    engine = create_async_engine(f"sqlite+aiosqlite:///{migrated_db.as_posix()}")
    async with engine.begin() as conn:
        await conn.execute(clients.delete())

    # get_client reads the application's module-level engine, so point it here.
    monkeypatch.setattr(clients_db, "engine", engine)
    yield engine
    await engine.dispose()


def make_client(**overrides) -> Client:
    return Client(
        **{
            "client_id": "test-client",
            "client_type": "confidential",
            "hashed_secret": "not-a-real-hash",
            "allowed_scopes": ["read", "write"],
            **overrides,
        }
    )


async def test_migration_creates_a_usable_clients_table(db):
    assert await clients_db.list_clients(db) == []


async def test_created_client_round_trips(db):
    created = make_client()

    await clients_db.create_client(db, created)

    assert await clients_db.get_client("test-client") == created


async def test_list_fields_survive_the_round_trip(db):
    await clients_db.create_client(db, make_client(allowed_scopes=["read", "write", "admin"]))

    stored = await clients_db.get_client("test-client")

    # JSON columns, so these must come back as lists rather than a string.
    assert stored.allowed_scopes == ["read", "write", "admin"]
    assert stored.allowed_grants == ["client_credentials"]


async def test_get_client_returns_none_for_an_unknown_id(db):
    assert await clients_db.get_client("nope") is None


async def test_client_id_is_unique(db):
    await clients_db.create_client(db, make_client())

    with pytest.raises(IntegrityError):
        await clients_db.create_client(db, make_client(allowed_scopes=["read"]))


async def test_clients_are_enabled_by_default(db):
    await clients_db.create_client(db, make_client())

    assert (await clients_db.get_client("test-client")).enabled


async def test_disabling_a_client_persists(db):
    await clients_db.create_client(db, make_client())

    assert await clients_db.set_client_enabled(db, "test-client", False)
    assert not (await clients_db.get_client("test-client")).enabled


async def test_disabling_an_unknown_client_reports_no_match(db):
    assert not await clients_db.set_client_enabled(db, "nope", False)


async def test_list_clients_is_ordered_by_id(db):
    await clients_db.create_client(db, make_client(client_id="zulu"))
    await clients_db.create_client(db, make_client(client_id="alpha"))

    assert [client.client_id for client in await clients_db.list_clients(db)] == ["alpha", "zulu"]
