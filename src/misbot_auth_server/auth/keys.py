"""Signing key material and the public JWK that resource servers verify against."""

import hashlib
import json
from functools import cache
from typing import Any

from cryptography.hazmat.primitives import serialization
from jwt.algorithms import get_default_algorithms
from jwt.utils import base64url_encode

from misbot_auth_server.settings import settings

# RFC 7638 §3.2: the members a thumbprint is computed over, per key type.
THUMBPRINT_MEMBERS = {
    "RSA": ("e", "kty", "n"),
    "EC": ("crv", "kty", "x", "y"),
}


def _thumbprint(jwk: dict[str, Any]) -> str:
    """Return the RFC 7638 SHA-256 thumbprint of a JWK, used as its key ID."""
    kty = jwk["kty"]
    if kty not in THUMBPRINT_MEMBERS:
        raise ValueError(f"cannot compute a thumbprint for key type {kty!r}")

    # The hash input is the required members only, lexicographically ordered
    # and serialized without whitespace, so the ID is stable across restarts.
    canonical = json.dumps(
        {member: jwk[member] for member in THUMBPRINT_MEMBERS[kty]},
        separators=(",", ":"),
        sort_keys=True,
    )
    return base64url_encode(hashlib.sha256(canonical.encode()).digest()).decode()


@cache
def public_jwk() -> dict[str, Any]:
    """The public half of the signing key, as a JWK with a stable ``kid``."""
    algorithm = get_default_algorithms()[settings.jwt.algorithm]
    private_key = serialization.load_pem_private_key(
        settings.jwt.private_key.get_secret_value().encode(),
        password=None,
    )

    jwk = algorithm.to_jwk(private_key.public_key(), as_dict=True)
    # `use` is the more widely consumed of the two, and RFC 7517 §4.3 requires
    # them to agree if both are present, so publish only `use`.
    jwk.pop("key_ops", None)
    jwk["use"] = "sig"
    jwk["alg"] = settings.jwt.algorithm
    jwk["kid"] = _thumbprint(jwk)
    return jwk


def key_id() -> str:
    """The ``kid`` that signed tokens carry, so verifiers can select the key."""
    return public_jwk()["kid"]


def jwks() -> dict[str, list[dict[str, Any]]]:
    """The JWK Set served to resource servers."""
    return {"keys": [public_jwk()]}
