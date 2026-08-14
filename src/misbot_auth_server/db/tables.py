"""Database schema, defined with SQLAlchemy Core.

Column names match the fields of :class:`misbot_auth_server.models.clients.Client`
exactly, so a row converts with ``Client(**row._mapping)`` and needs no mapping layer.
"""

from sqlalchemy import JSON, Boolean, Column, MetaData, String, Table, text

metadata = MetaData()

clients = Table(
    "clients",
    metadata,
    Column("client_id", String, primary_key=True),
    Column("client_type", String, nullable=False),
    Column("hashed_secret", String, nullable=False),
    # SQLite has no array type. These lists are short, never queried by element,
    # and always read whole, so JSON beats the association tables it would
    # otherwise take to store them.
    Column("allowed_scopes", JSON, nullable=False),
    Column("allowed_grants", JSON, nullable=False),
    Column("enabled", Boolean, nullable=False, server_default=text("1")),
)
