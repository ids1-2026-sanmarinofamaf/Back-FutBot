from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler
from app.api import auth, users, friendly_games, sessions_websocket
from app.services.startup_service import recover_interrupted_games


from sqlalchemy import text

from app.database import engine
from app.api import friendly_games, players
from app.api import behaviors
from app.api import leagues



from app.api.friendly_game_websocket import router as friendly_game_websocket_router
from app.api.match_websocket import router as match_websocket_router




# Se ejecuta una vez al arrancar la app y una vez al apagar
from fastapi.middleware.cors import CORSMiddleware

# Runs once when the app starts and once when it shuts down
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. STARTUP: runs before the server accepts requests
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

    recover_interrupted_games()
    yield
    # 2. SHUTDOWN: runs while the server is shutting down (Ctrl+C, deploy, etc.)
    engine.dispose()

app = FastAPI(lifespan=lifespan)


# POST /leagues must answer 400 on an invalid body; every other endpoint keeps FastAPI's default 422
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    response = await request_validation_exception_handler(request, exc)
    if request.method == "POST" and request.url.path == "/leagues":
        response.status_code = status.HTTP_400_BAD_REQUEST
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tu origen de Vite
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(sessions_websocket.router)
app.include_router(friendly_game_websocket_router)
app.include_router(behaviors.router)
app.include_router(leagues.router)


@app.get("/")
def root():
    return{"message": "FutBot backend running"}


app.include_router(friendly_games.router)
app.include_router(players.router)
app.include_router(match_websocket_router)
