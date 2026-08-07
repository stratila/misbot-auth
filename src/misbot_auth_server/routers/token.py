from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import APIRouter, Form, Header, Response

from misbot_auth_server.auth.client_auth import resolve_client_credentials
from misbot_auth_server.auth.errors import NO_STORE_HEADERS, OAuth2Error, invalid_client
from misbot_auth_server.auth.keys import key_id
from misbot_auth_server.auth.passwords import authenticate_client
from misbot_auth_server.models.clients import Client
from misbot_auth_server.schemas.token import ClientCredentialsForm, TokenResponse
from misbot_auth_server.settings import settings

CLIENT_CREDENTIALS_GRANT = "client_credentials"

token_router = APIRouter(tags=["token"])


def _granted_scopes(requested: str | None, client: Client) -> list[str]:
    """Validate the requested scopes, defaulting to everything the client may have."""
    # An absent or empty `scope` lets the server pick, per RFC 6749 §3.3.
    scopes = requested.split() if requested else []
    if not scopes:
        return list(client.allowed_scopes)

    for scope in scopes:
        if scope not in client.allowed_scopes:
            raise OAuth2Error("invalid_scope", f"scope {scope!r} is not allowed for this client")

    return scopes


@token_router.post("/token")
async def token(
    response: Response,
    form_data: Annotated[ClientCredentialsForm, Form()],
    authorization: Annotated[str | None, Header()] = None,
) -> TokenResponse:
    if form_data.grant_type != CLIENT_CREDENTIALS_GRANT:
        raise OAuth2Error(
            "unsupported_grant_type",
            f"grant type {form_data.grant_type!r} is not supported",
        )

    credentials = resolve_client_credentials(
        authorization,
        form_data.client_id,
        form_data.client_secret,
    )

    client = authenticate_client(credentials.client_id, credentials.client_secret)
    if client is None:
        raise invalid_client(
            "client authentication failed",
            used_basic_auth=credentials.used_basic_auth,
        )

    # Registration policy is checked only after authentication, so an
    # unauthenticated caller cannot probe a client's existence or state.
    if not client.enabled:
        raise invalid_client(
            "client authentication failed",
            used_basic_auth=credentials.used_basic_auth,
        )

    # Public clients cannot keep a secret confidential, so RFC 6749 §4.4
    # restricts this grant to confidential clients registered to use it.
    if (
        client.client_type != "confidential"
        or CLIENT_CREDENTIALS_GRANT not in client.allowed_grants
    ):
        raise OAuth2Error(
            "unauthorized_client",
            "this client may not use the client credentials grant",
        )

    granted_scopes = _granted_scopes(form_data.scope, client)

    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=settings.jwt.access_token_expire_minutes)

    payload = {
        "iss": settings.jwt.issuer,
        "aud": settings.jwt.audience,
        "sub": client.client_id,
        "iat": now,
        "exp": expires_at,
        "scope": " ".join(granted_scopes),
    }

    access_token = jwt.encode(
        payload,
        settings.jwt.private_key.get_secret_value(),
        algorithm=settings.jwt.algorithm,
        # Names the signing key so verifiers can pick it out of the JWK Set,
        # which is what makes rotating keys possible without downtime.
        headers={"kid": key_id()},
    )

    # §5.1 requires tokens never be cached by intermediaries.
    response.headers.update(NO_STORE_HEADERS)

    return TokenResponse(
        access_token=access_token,
        expires_in=settings.jwt.access_token_expire_minutes * 60,
        scope=" ".join(granted_scopes),
    )
