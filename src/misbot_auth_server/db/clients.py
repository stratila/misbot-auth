"""Queries against the registered OAuth clients."""

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from misbot_auth_server.db.engine import engine
from misbot_auth_server.db.tables import clients
from misbot_auth_server.models.clients import Client


async def get_client(client_id: str) -> Client | None:
    async with engine.connect() as conn:
        result = await conn.execute(select(clients).where(clients.c.client_id == client_id))
        row = result.fetchone()

    return Client(**row._mapping) if row else None


# The functions below back the admin CLI, which runs against a database the
# server may not be holding open, so they take the engine explicitly.


async def create_client(db: AsyncEngine, client: Client) -> None:
    """Insert a client. Raises ``IntegrityError`` if the id is already taken."""
    async with db.begin() as conn:
        await conn.execute(clients.insert().values(**client.model_dump()))


async def list_clients(db: AsyncEngine) -> list[Client]:
    async with db.connect() as conn:
        result = await conn.execute(select(clients).order_by(clients.c.client_id))
        rows = result.fetchall()

    return [Client(**row._mapping) for row in rows]


async def set_client_enabled(db: AsyncEngine, client_id: str, enabled: bool) -> bool:
    """Enable or disable a client, returning whether one was found."""
    async with db.begin() as conn:
        result = await conn.execute(
            update(clients).where(clients.c.client_id == client_id).values(enabled=enabled)
        )

    return result.rowcount > 0
