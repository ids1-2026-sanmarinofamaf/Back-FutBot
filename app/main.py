from contextlib import asynccontextmanager

from fastapi import FastAPI
from app.api import auth, users

from sqlalchemy import text

from app.database import engine

# Se ejecuta una vez al arrancar la app y una vez al apagar
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. STARTUP: corre antes de que el servidor acepte requests
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    yield
    # 2. SHUTDOWN: corre cuando el servidor se está apagando (Ctrl+C, deploy, etc.)
    engine.dispose()

app = FastAPI(lifespan=lifespan)

app.include_router(auth.router)
app.include_router(users.router)

@app.get("/")
def root():
    return{"message": "FutBot backend running"}