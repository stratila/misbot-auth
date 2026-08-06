from pydantic import BaseModel


class Client(BaseModel):
    client_id: str
    client_type: str
    hashed_secret: str
    allowed_scopes: list[str]
    allowed_grants: list[str] = ["client_credentials"]
    enabled: bool = True
