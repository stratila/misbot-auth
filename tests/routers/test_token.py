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
    return client.post("/token", data={k: v for k, v in data.items() if v is not None})


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


def test_token_response_is_not_cacheable(client, registered_client):
    response = token_request(client)

    # RFC 6749 §5.1: access tokens must never be stored by intermediaries.
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"


def test_token_rejects_unsupported_grant_type(client, registered_client):
    response = token_request(client, grant_type="password")

    assert response.status_code == 400
    assert response.json()["error"] == "unsupported_grant_type"


def test_token_rejects_wrong_client_secret(client, registered_client):
    response = token_request(client, client_secret="wrong")

    assert response.status_code == 401
    assert response.json()["error"] == "invalid_client"


def test_token_rejects_unknown_client(client, registered_client):
    response = token_request(client, client_id="nope")

    assert response.status_code == 401
    assert response.json()["error"] == "invalid_client"


def test_token_rejects_disallowed_scope(client, registered_client):
    response = token_request(client, scope="admin")

    assert response.status_code == 400
    assert response.json()["error"] == "invalid_scope"


def test_token_rejects_disabled_client(client, register_client):
    register_client(enabled=False)

    response = token_request(client)

    assert response.status_code == 401
    assert response.json()["error"] == "invalid_client"


def test_token_rejects_public_client(client, register_client):
    register_client(client_type="public")

    response = token_request(client)

    assert response.status_code == 400
    assert response.json()["error"] == "unauthorized_client"


def test_token_rejects_client_not_registered_for_the_grant(client, register_client):
    register_client(allowed_grants=["authorization_code"])

    response = token_request(client)

    assert response.status_code == 400
    assert response.json()["error"] == "unauthorized_client"


def test_error_response_is_not_cacheable(client, registered_client):
    response = token_request(client, client_secret="wrong")

    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"


def test_error_response_carries_a_description(client, registered_client):
    response = token_request(client, grant_type="password")

    assert "error_description" in response.json()


def test_missing_grant_type_is_an_invalid_request(client, registered_client):
    response = client.post("/token", data={"client_id": "test-client", "client_secret": "s3cret"})

    # Not FastAPI's 422 validation blob, which no OAuth client can parse.
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_request"


def test_token_response_shape_is_documented(client):
    schema = client.get("/openapi.json").json()
    ref = schema["paths"]["/token"]["post"]["responses"]["200"]["content"]["application/json"][
        "schema"
    ]["$ref"]

    # A bare dict return would document the response as an empty object, leaving
    # generated clients with nothing to deserialize into.
    documented = schema["components"]["schemas"][ref.rsplit("/", 1)[-1]]
    assert set(documented["properties"]) == {"access_token", "token_type", "expires_in", "scope"}


class TestScopeDefaulting:
    def test_omitted_scope_grants_every_allowed_scope(self, client, registered_client):
        response = token_request(client, scope=None)

        assert response.status_code == 200
        assert response.json()["scope"] == "read write"

    def test_empty_scope_grants_every_allowed_scope(self, client, registered_client):
        response = token_request(client, scope="")

        assert response.status_code == 200
        assert response.json()["scope"] == "read write"

    def test_subset_of_allowed_scopes_is_granted_as_requested(self, client, registered_client):
        response = token_request(client, scope="write")

        assert response.status_code == 200
        assert response.json()["scope"] == "write"

    def test_one_disallowed_scope_rejects_the_whole_request(self, client, registered_client):
        response = token_request(client, scope="read admin")

        assert response.status_code == 400
        assert response.json()["error"] == "invalid_scope"
