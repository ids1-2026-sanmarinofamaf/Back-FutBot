from contextlib import asynccontextmanager

from fastapi import FastAPI
from app.api import auth, users, friendly_games, sessions_websocket


from sqlalchemy import text

from app.database import engine
from app.api import friendly_games, players



from app.api.match_websocket import router as match_websocket_router




# Se ejecuta una vez al arrancar la app y una vez al apagar
from fastapi.middleware.cors import CORSMiddleware

# Runs once when the app starts and once when it shuts down
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. STARTUP: runs before the server accepts requests
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    yield
    # 2. SHUTDOWN: runs while the server is shutting down (Ctrl+C, deploy, etc.)
    engine.dispose()

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # tu origen de Vite
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(sessions_websocket.router)


@app.get("/")
def root():
    return{"message": "FutBot backend running"}


app.include_router(friendly_games.router)
app.include_router(players.router)
app.include_router(match_websocket_router)
