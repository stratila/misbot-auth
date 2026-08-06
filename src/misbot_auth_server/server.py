from fastapi import FastAPI

from misbot_auth_server.auth.discovery import discovery_router
from misbot_auth_server.auth.router import auth_router

app = FastAPI()
app.include_router(auth_router)
app.include_router(discovery_router)


@app.get("/")
async def root():
    return {"message": "Hello from misbot-auth-server"}
