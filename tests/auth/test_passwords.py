from misbot_auth_server.auth.passwords import (
    authenticate_client,
    get_password_hash,
    verify_password,
)
from misbot_auth_server.models.clients import Client


def test_get_password_hash_round_trips_through_verify_password():
    hashed = get_password_hash("s3cret")

    assert verify_password("s3cret", hashed)


def test_verify_password_rejects_wrong_password():
    hashed = get_password_hash("s3cret")

    assert not verify_password("wrong", hashed)


def _known_client(monkeypatch) -> Client:
    """Make one client resolvable through the patched lookup."""
    client = Client(
        client_id="test-client",
        client_type="confidential",
        hashed_secret=get_password_hash("s3cret"),
        allowed_scopes=["read"],
    )

    async def _get_client(client_id):
        return client if client_id == "test-client" else None

    monkeypatch.setattr("misbot_auth_server.auth.passwords.get_client", _get_client)
    return client


async def test_authenticate_client_returns_client_on_valid_secret(monkeypatch):
    client = _known_client(monkeypatch)

    assert await authenticate_client("test-client", "s3cret") == client


async def test_authenticate_client_rejects_wrong_secret(monkeypatch):
    _known_client(monkeypatch)

    assert await authenticate_client("test-client", "wrong") is None


async def test_authenticate_client_rejects_unknown_client(monkeypatch):
    async def _get_client(client_id):
        return None

    monkeypatch.setattr("misbot_auth_server.auth.passwords.get_client", _get_client)

    assert await authenticate_client("nope", "whatever") is None
