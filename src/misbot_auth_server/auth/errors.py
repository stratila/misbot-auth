"""OAuth 2.0 error responses, as specified by RFC 6749 §5.2."""

from fastapi import Request, status
from fastapi.responses import JSONResponse

# RFC 6749 §5.1 and §5.2 require token endpoint responses to be uncacheable.
# `Pragma` is legacy HTTP, but the RFC names it explicitly, so send both.
NO_STORE_HEADERS = {"Cache-Control": "no-store", "Pragma": "no-cache"}


class OAuth2Error(Exception):
    """An error rendered in the form the OAuth 2.0 spec requires."""

    def __init__(
        self,
        error: str,
        description: str | None = None,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(error)
        self.error = error
        self.description = description
        self.status_code = status_code
        self.headers = headers or {}


def invalid_client(description: str, *, used_basic_auth: bool = False) -> OAuth2Error:
    """Build a 401 ``invalid_client`` error.

    RFC 6749 §5.2 requires a matching ``WWW-Authenticate`` header whenever the
    client tried to authenticate through the ``Authorization`` header.
    """
    headers = {"WWW-Authenticate": "Basic"} if used_basic_auth else None
    return OAuth2Error(
        "invalid_client",
        description,
        status_code=status.HTTP_401_UNAUTHORIZED,
        headers=headers,
    )


async def oauth2_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, OAuth2Error)

    body = {"error": exc.error}
    if exc.description:
        body["error_description"] = exc.description

    return JSONResponse(
        body,
        status_code=exc.status_code,
        headers={**NO_STORE_HEADERS, **exc.headers},
    )


async def validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Render malformed requests as ``invalid_request`` rather than FastAPI's 422."""
    return await oauth2_error_handler(
        request,
        OAuth2Error("invalid_request", "the request is missing a required parameter"),
    )
