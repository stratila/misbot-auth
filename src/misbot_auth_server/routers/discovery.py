"""Public discovery endpoints: key distribution and server metadata."""

from fastapi import APIRouter

from misbot_auth_server.auth.keys import jwks
from misbot_auth_server.settings import settings

JWKS_PATH = "/.well-known/jwks.json"
METADATA_PATH = "/.well-known/oauth-authorization-server"
TOKEN_PATH = "/token"

discovery_router = APIRouter(tags=["discovery"])


def _url(path: str) -> str:
    return f"{settings.jwt.issuer.rstrip('/')}{path}"


@discovery_router.get(JWKS_PATH)
async def jwks_document():
    return jwks()


@discovery_router.get(METADATA_PATH)
async def authorization_server_metadata():
    """RFC 8414 metadata, so clients can discover this server automatically."""
    return {
        "issuer": settings.jwt.issuer,
        "token_endpoint": _url(TOKEN_PATH),
        "jwks_uri": _url(JWKS_PATH),
        "grant_types_supported": ["client_credentials"],
        # This server has no authorization endpoint, so it supports no
        # response types; the member is required, so report it as empty.
        "response_types_supported": [],
        "token_endpoint_auth_methods_supported": ["client_secret_basic", "client_secret_post"],
    }
