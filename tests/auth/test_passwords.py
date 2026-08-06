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


def test_authenticate_client_returns_client_on_valid_secret(monkeypatch):
    client = Client(
        client_id="test-client",
        client_type="confidential",
        hashed_secret=get_password_hash("s3cret"),
        allowed_scopes=["read"],
    )
    monkeypatch.setattr(
        "misbot_auth_server.auth.passwords.get_client",
        lambda client_id: client if client_id == "test-client" else None,
    )

    assert authenticate_client("test-client", "s3cret") == client


def test_authenticate_client_rejects_wrong_secret(monkeypatch):
    client = Client(
        client_id="test-client",
        client_type="confidential",
        hashed_secret=get_password_hash("s3cret"),
        allowed_scopes=["read"],
    )
    monkeypatch.setattr(
        "misbot_auth_server.auth.passwords.get_client",
        lambda client_id: client if client_id == "test-client" else None,
    )

    assert authenticate_client("test-client", "wrong") is False


def test_authenticate_client_rejects_unknown_client(monkeypatch):
    monkeypatch.setattr("misbot_auth_server.auth.passwords.get_client", lambda client_id: None)

    assert authenticate_client("nope", "whatever") is False
