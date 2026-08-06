import pytest
from fastapi.testclient import TestClient

from misbot_auth_server.auth.passwords import get_password_hash
from misbot_auth_server.models.clients import Client
from misbot_auth_server.server import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def register_client(monkeypatch):
    """Register a client with the given overrides as the only known client."""

    def _register(**overrides):
        client = Client(
            **{
                "client_id": "test-client",
                "client_type": "confidential",
                "hashed_secret": get_password_hash("s3cret"),
                "allowed_scopes": ["read", "write"],
                **overrides,
            }
        )
        monkeypatch.setattr(
            "misbot_auth_server.auth.passwords.get_client",
            lambda client_id: client if client_id == client.client_id else None,
        )
        return client

    return _register


@pytest.fixture
def registered_client(register_client):
    return register_client()
