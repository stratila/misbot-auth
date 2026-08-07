from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from misbot_auth_server.auth.errors import (
    OAuth2Error,
    oauth2_error_handler,
    validation_error_handler,
)
from misbot_auth_server.db.engine import engine
from misbot_auth_server.routers import ROUTERS


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    # Close pooled SQLite connections rather than leaving them to the garbage
    # collector, which would run them on the wrong event loop.
    await engine.dispose()


app = FastAPI(lifespan=lifespan)

for router in ROUTERS:
    app.include_router(router)

app.add_exception_handler(OAuth2Error, oauth2_error_handler)
# This server only accepts input at the token endpoint, so a malformed request
# is always an OAuth error and should be rendered in the OAuth error shape.
app.add_exception_handler(RequestValidationError, validation_error_handler)


@app.get("/")
async def root():
    return {"message": "Hello from misbot-auth-server"}
