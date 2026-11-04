from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api import (
    auth,
    users,
    friendly_games,
    players,
    sessions_websocket,
    matches,
    behaviors,
    behavior_preview,
    leagues,
    ranking,
)
from app.api.friendly_game_websocket import router as friendly_game_websocket_router
from app.api.match_websocket import router as match_websocket_router
from app.api.behavior_preview_websocket import router as behavior_preview_websocket_router
from app.api.league_websocket import router as league_websocket_router
from app.database import engine
from app.services.league_runner import stop_league_runners
from app.services.startup_service import (
    recover_interrupted_games,
    recover_interrupted_leagues,
)
from app.services.match_service import (
    initialize_worker_pool,
    shutdown_worker_pool,
    stop_running_matches,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

    recover_interrupted_games()
    initialize_worker_pool()

    try:
        recover_interrupted_leagues()
        yield
    finally:
        await stop_league_runners()
        await stop_running_matches()
        shutdown_worker_pool()
        engine.dispose()


app = FastAPI(lifespan=lifespan)


# POST /leagues must answer 400 on an invalid body; other endpoints keep 422.
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    response = await request_validation_exception_handler(request, exc)
    if request.method == "POST" and request.url.path == "/leagues":
        response.status_code = status.HTTP_400_BAD_REQUEST
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(sessions_websocket.router)
app.include_router(friendly_game_websocket_router)
app.include_router(behavior_preview.router)
app.include_router(behaviors.router)
app.include_router(leagues.router)
app.include_router(ranking.router)
app.include_router(league_websocket_router)
app.include_router(friendly_games.router)
app.include_router(players.router)
app.include_router(matches.router)
app.include_router(match_websocket_router)
app.include_router(behavior_preview_websocket_router)


@app.get("/")
def root():
    return {"message": "FutBot backend running"}
