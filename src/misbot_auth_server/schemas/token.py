"""Wire format of the token endpoint, as defined by RFC 6749 §4.4."""

from pydantic import BaseModel


class ClientCredentialsForm(BaseModel):
    grant_type: str
    # Credentials are optional here because RFC 6749 §2.3.1 prefers them in the
    # `Authorization` header; `scope` is optional per §4.4.2.
    client_id: str | None = None
    client_secret: str | None = None
    scope: str | None = None


class TokenResponse(BaseModel):
    """A successful token response, per RFC 6749 §5.1."""

    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    # §5.1 only requires `scope` when it differs from what was requested, but
    # sending it always saves clients from having to track that themselves.
    scope: str
