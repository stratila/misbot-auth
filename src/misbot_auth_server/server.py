from fastapi import FastAPI

from misbot_auth_server.auth.router import auth_router

app = FastAPI()
app.include_router(auth_router)


@app.get("/")
async def root():
    return {"message": "Hello from misbot-auth-server"}
