from typing import Literal

from pydantic import BaseModel


class Client(BaseModel):
    client_id: str
    client_type: Literal["confidential", "public"]
    hashed_secret: str
    allowed_scopes: list[str]
    allowed_grants: list[str] = ["client_credentials"]
    enabled: bool = True
