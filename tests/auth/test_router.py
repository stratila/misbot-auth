import jwt

from misbot_auth_server.settings import settings


def token_request(client, **overrides):
    data = {
        "grant_type": "client_credentials",
        "client_id": "test-client",
        "client_secret": "s3cret",
        "scope": "read",
        **overrides,
    }
    return client.post("/token", data=data)


def test_token_issues_access_token_for_valid_client(client, registered_client):
    response = token_request(client)

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "Bearer"
    assert body["scope"] == "read"
    assert body["expires_in"] == settings.jwt.access_token_expire_minutes * 60

    payload = jwt.decode(body["access_token"], options={"verify_signature": False})
    assert payload["sub"] == "test-client"
    assert payload["scope"] == "read"
    assert payload["iss"] == settings.jwt.issuer
    assert payload["aud"] == settings.jwt.audience


def test_token_rejects_unsupported_grant_type(client, registered_client):
    response = token_request(client, grant_type="password")

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid_client"


def test_token_rejects_wrong_client_secret(client, registered_client):
    response = token_request(client, client_secret="wrong")

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid_client"


def test_token_rejects_unknown_client(client, registered_client):
    response = token_request(client, client_id="nope")

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid_client"


def test_token_rejects_disallowed_scope(client, registered_client):
    response = token_request(client, scope="admin")

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid_scope"


def test_token_rejects_disabled_client(client, register_client):
    register_client(enabled=False)

    response = token_request(client)

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid_client"


def test_token_rejects_public_client(client, register_client):
    register_client(client_type="public")

    response = token_request(client)

    assert response.status_code == 401
    assert response.json()["detail"] == "unauthorized_client"


def test_token_rejects_client_not_registered_for_the_grant(client, register_client):
    register_client(allowed_grants=["authorization_code"])

    response = token_request(client)

    assert response.status_code == 401
    assert response.json()["detail"] == "unauthorized_client"
