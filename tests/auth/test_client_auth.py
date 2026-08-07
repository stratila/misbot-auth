from base64 import b64encode
from urllib.parse import quote


def basic_header(client_id, client_secret):
    """Build an RFC 6749 §2.3.1 Basic header, form-urlencoding each half."""
    raw = f"{quote(client_id)}:{quote(client_secret)}"
    return "Basic " + b64encode(raw.encode()).decode()


def post_token(client, headers=None, **body):
    data = {"grant_type": "client_credentials", **body}
    return client.post("/token", data=data, headers=headers or {})


def test_basic_auth_issues_a_token(client, registered_client):
    response = post_token(client, headers={"Authorization": basic_header("test-client", "s3cret")})

    assert response.status_code == 200
    assert response.json()["token_type"] == "Bearer"


def test_basic_auth_secret_containing_a_colon_round_trips(client, register_client):
    register_client(secret="s3:cret")

    response = post_token(client, headers={"Authorization": basic_header("test-client", "s3:cret")})

    # Without percent-decoding, the secret would be truncated at the colon.
    assert response.status_code == 200


def test_basic_auth_rejects_a_wrong_secret(client, registered_client):
    response = post_token(client, headers={"Authorization": basic_header("test-client", "wrong")})

    assert response.status_code == 401
    assert response.json()["error"] == "invalid_client"


def test_rejection_of_basic_auth_challenges_the_client(client, registered_client):
    response = post_token(client, headers={"Authorization": basic_header("test-client", "wrong")})

    # RFC 6749 §5.2 requires a challenge when the Authorization header was used.
    assert response.headers["www-authenticate"] == "Basic"


def test_rejection_of_post_auth_does_not_challenge_the_client(client, registered_client):
    response = post_token(client, client_id="test-client", client_secret="wrong")

    assert response.status_code == 401
    assert "www-authenticate" not in response.headers


def test_using_both_authentication_methods_is_rejected(client, registered_client):
    response = post_token(
        client,
        headers={"Authorization": basic_header("test-client", "s3cret")},
        client_id="test-client",
        client_secret="s3cret",
    )

    # §2.3 allows only one method; accepting both would let a caller try two
    # secrets in a single request.
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_request"


def test_missing_credentials_are_rejected(client, registered_client):
    response = post_token(client)

    assert response.status_code == 401
    assert response.json()["error"] == "invalid_client"


def test_client_id_without_a_secret_is_rejected(client, registered_client):
    response = post_token(client, client_id="test-client")

    assert response.status_code == 401
    assert response.json()["error"] == "invalid_client"


def test_malformed_basic_credentials_are_rejected(client, registered_client):
    response = post_token(client, headers={"Authorization": "Basic not-valid-base64!!"})

    assert response.status_code == 401
    assert response.json()["error"] == "invalid_client"


def test_basic_credentials_without_a_colon_are_rejected(client, registered_client):
    encoded = b64encode(b"no-separator-here").decode()

    response = post_token(client, headers={"Authorization": f"Basic {encoded}"})

    assert response.status_code == 401
    assert response.json()["error"] == "invalid_client"


def test_unsupported_authentication_scheme_is_rejected(client, registered_client):
    response = post_token(client, headers={"Authorization": "Bearer some-token"})

    assert response.status_code == 401
    assert response.json()["error"] == "invalid_client"
