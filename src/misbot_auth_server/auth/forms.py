from pydantic import BaseModel


class ClientCredentialsForm(BaseModel):
    grant_type: str
    # Credentials are optional here because RFC 6749 §2.3.1 prefers them in the
    # `Authorization` header; `scope` is optional per §4.4.2.
    client_id: str | None = None
    client_secret: str | None = None
    scope: str | None = None
