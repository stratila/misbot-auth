"""Resolving client credentials from a token request (RFC 6749 §2.3.1)."""

import binascii
from base64 import b64decode
from dataclasses import dataclass
from urllib.parse import unquote

from misbot_auth_server.auth.errors import OAuth2Error, invalid_client


@dataclass(frozen=True)
class ClientCredentials:
    client_id: str
    client_secret: str
    # Whether Basic was used, which decides if a rejection carries
    # `WWW-Authenticate` back to the client.
    used_basic_auth: bool


def _from_basic_auth(header: str) -> ClientCredentials:
    scheme, _, param = header.partition(" ")
    if scheme.lower() != "basic":
        raise invalid_client("unsupported authentication scheme", used_basic_auth=True)

    try:
        decoded = b64decode(param, validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError) as exc:
        raise invalid_client("malformed Basic credentials", used_basic_auth=True) from exc

    client_id, separator, client_secret = decoded.partition(":")
    if not separator:
        raise invalid_client("malformed Basic credentials", used_basic_auth=True)

    # §2.3.1 requires both halves to be form-urlencoded before base64 encoding,
    # so that a secret containing a colon survives the round trip.
    return ClientCredentials(unquote(client_id), unquote(client_secret), used_basic_auth=True)


def resolve_client_credentials(
    authorization: str | None,
    client_id: str | None,
    client_secret: str | None,
) -> ClientCredentials:
    """Take the client's credentials from exactly one supported location."""
    from_body = client_id is not None or client_secret is not None

    # §2.3 forbids using more than one authentication method in a request;
    # accepting both would let a caller probe two secrets in one call.
    if authorization is not None and from_body:
        raise OAuth2Error(
            "invalid_request",
            "more than one client authentication method used",
        )

    if authorization is not None:
        return _from_basic_auth(authorization)

    if client_id is None or client_secret is None:
        raise invalid_client("client authentication failed")

    return ClientCredentials(client_id, client_secret, used_basic_auth=False)
