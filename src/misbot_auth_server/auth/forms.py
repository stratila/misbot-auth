from pydantic import BaseModel


class ClientCredentialsForm(BaseModel):
    client_id: str
    client_secret: str
    grant_type: str
    scope: str
