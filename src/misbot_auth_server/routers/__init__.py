"""HTTP routes, one module per endpoint group.

Route modules hold only request handling; the OAuth logic they call lives in
:mod:`misbot_auth_server.auth`.
"""

from misbot_auth_server.routers.discovery import discovery_router
from misbot_auth_server.routers.token import token_router

# Every router the application serves, in the order they are mounted.
ROUTERS = (token_router, discovery_router)

__all__ = ["ROUTERS", "discovery_router", "token_router"]
