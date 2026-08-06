from misbot_auth_server.db import fake_clients_db
from misbot_auth_server.models.clients import Client


def get_client(client_id) -> Client | None:
    if client_id in fake_clients_db:
        return Client(**fake_clients_db[client_id])
