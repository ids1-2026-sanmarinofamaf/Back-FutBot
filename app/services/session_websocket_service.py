from fastapi import WebSocket
from sqlalchemy.orm import Session

from app.core.ws_manager import manager
from app.repositories import friendly_game_repository
from app.schemas.friendly_game import (
    FriendlyGameSessionItem,
    FriendlyGamesSessionPayload,
)


def build_friendly_games_payload(
    db: Session,
) -> FriendlyGamesSessionPayload:

    friendly_games = (
        friendly_game_repository.get_visible_friendly_games(db)
    )

    return FriendlyGamesSessionPayload(
        friendly_games=[
            FriendlyGameSessionItem(
                friendly_game_id=friendly_game.id,
                creator_club_name=friendly_game.creator.name,
                current_participants=len(
                    friendly_game.participations
                ),
                capacity=2,
                state=friendly_game.state,
            )
            for friendly_game in friendly_games
        ]
    )

# send the message when the user connects
async def send_friendly_games_to_connection(
    websocket: WebSocket,
    db: Session,
) -> None:

    payload = build_friendly_games_payload(db)

    await websocket.send_json(
        payload.model_dump(mode="json")
    )

# send to all the connections
async def broadcast_friendly_games(
    db: Session,
) -> None:

    payload = build_friendly_games_payload(db)

    await manager.broadcast_json(
        payload.model_dump(mode="json")
    )