from base64 import b64encode

import jwt
import pytest
from jwt import PyJWKSet

from misbot_auth_server.settings import settings


def issue_token(client):
    response = client.post(
        "/token",
        data={
            "grant_type": "client_credentials",
            "client_id": "test-client",
            "client_secret": "s3cret",
            "scope": "read",
        },
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_jwks_document_publishes_one_usable_signing_key(client):
    document = client.get("/.well-known/jwks.json").json()

    assert len(document["keys"]) == 1
    key = document["keys"][0]
    assert key["kty"] == "RSA"
    assert key["use"] == "sig"
    assert key["alg"] == settings.jwt.algorithm
    assert key["kid"]


def test_jwks_document_never_exposes_private_key_material(client):
    key = client.get("/.well-known/jwks.json").json()["keys"][0]

    # RFC 7518 §6.3.2: these members only ever appear on a private RSA key.
    for private_member in ("d", "p", "q", "dp", "dq", "qi"):
        assert private_member not in key


def test_token_header_names_a_key_present_in_the_jwks(client, registered_client):
    token = issue_token(client)
    document = client.get("/.well-known/jwks.json").json()

    kid = jwt.get_unverified_header(token)["kid"]
    assert kid in {key["kid"] for key in document["keys"]}


def test_issued_token_verifies_against_the_published_jwks(client, registered_client):
    """The whole point of Tier 2: a resource server can verify our tokens."""
    token = issue_token(client)
    document = client.get("/.well-known/jwks.json").json()

    # Exactly what a resource server does: select the key by `kid`, then verify.
    kid = jwt.get_unverified_header(token)["kid"]
    signing_key = next(key for key in PyJWKSet.from_dict(document).keys if key.key_id == kid)

    payload = jwt.decode(
        token,
        signing_key.key,
        algorithms=[settings.jwt.algorithm],
        audience=settings.jwt.audience,
        issuer=settings.jwt.issuer,
    )

    assert payload["sub"] == "test-client"
    assert payload["scope"] == "read"


def test_tampered_token_fails_verification_against_the_jwks(client, registered_client):
    token = issue_token(client)
    document = client.get("/.well-known/jwks.json").json()
    signing_key = PyJWKSet.from_dict(document).keys[0]

    header, payload, signature = token.split(".")
    tampered = f"{header}.{payload}.{signature[:-4]}AAAA"

    with pytest.raises(jwt.InvalidSignatureError):
        jwt.decode(
            tampered,
            signing_key.key,
            algorithms=[settings.jwt.algorithm],
            audience=settings.jwt.audience,
            issuer=settings.jwt.issuer,
        )


def test_metadata_advertises_the_token_endpoint_and_jwks(client):
    metadata = client.get("/.well-known/oauth-authorization-server").json()

    assert metadata["issuer"] == settings.jwt.issuer
    assert metadata["token_endpoint"] == f"{settings.jwt.issuer}/token"
    assert metadata["jwks_uri"] == f"{settings.jwt.issuer}/.well-known/jwks.json"
    assert metadata["grant_types_supported"] == ["client_credentials"]


def test_metadata_advertises_both_supported_auth_methods(client, registered_client):
    metadata = client.get("/.well-known/oauth-authorization-server").json()

    assert set(metadata["token_endpoint_auth_methods_supported"]) == {
        "client_secret_basic",
        "client_secret_post",
    }

    # Clients pick their auth method from this document, so both must work.
    body = {"grant_type": "client_credentials"}
    basic = b64encode(b"test-client:s3cret").decode()

    via_post = client.post(
        "/token",
        data={**body, "client_id": "test-client", "client_secret": "s3cret"},
    )
    via_basic = client.post("/token", data=body, headers={"Authorization": f"Basic {basic}"})

    assert via_post.status_code == 200
    assert via_basic.status_code == 200
