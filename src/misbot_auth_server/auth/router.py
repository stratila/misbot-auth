from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import APIRouter, Form, HTTPException, status

from misbot_auth_server.auth.forms import ClientCredentialsForm
from misbot_auth_server.auth.keys import key_id
from misbot_auth_server.auth.passwords import authenticate_client
from misbot_auth_server.settings import settings

CLIENT_CREDENTIALS_GRANT = "client_credentials"

auth_router = APIRouter()


@auth_router.post("/token")
async def token(form_data: Annotated[ClientCredentialsForm, Form()]):
    if form_data.grant_type != CLIENT_CREDENTIALS_GRANT:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_client",
        )

    client_id, client_secret = form_data.client_id, form_data.client_secret

    client = authenticate_client(client_id, client_secret)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_client",
        )

    # Registration policy is checked only after authentication, so an
    # unauthenticated caller cannot probe a client's existence or state.
    if not client.enabled:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_client",
        )

    # Public clients cannot keep a secret confidential, so RFC 6749 §4.4
    # restricts this grant to confidential clients registered to use it.
    if (
        client.client_type != "confidential"
        or CLIENT_CREDENTIALS_GRANT not in client.allowed_grants
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="unauthorized_client",
        )

    for scope in form_data.scope.split(" "):
        if scope not in client.allowed_scopes:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid_scope",
            )

    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=settings.jwt.access_token_expire_minutes)

    payload = {
        "iss": settings.jwt.issuer,
        "aud": settings.jwt.audience,
        "sub": client.client_id,
        "iat": now,
        "exp": expires_at,
        "scope": form_data.scope,
    }

    access_token = jwt.encode(
        payload,
        settings.jwt.private_key.get_secret_value(),
        algorithm=settings.jwt.algorithm,
        # Names the signing key so verifiers can pick it out of the JWK Set,
        # which is what makes rotating keys possible without downtime.
        headers={"kid": key_id()},
    )

    return {
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": settings.jwt.access_token_expire_minutes * 60,
        "scope": form_data.scope,
    }
