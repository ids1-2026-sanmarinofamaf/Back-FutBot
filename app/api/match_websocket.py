from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from app.database import SessionLocal
from app.services import auth_service
from app.repositories import club_repository
from app.services.match_websocket_service import match_connection_manager

# APIRouter is used to define the routes of this module separately and then add them to the main application.
router = APIRouter()


@router.websocket("/ws/matches/{match_id}")
async def match_websocket(
    websocket: WebSocket,
    match_id: int,
    token: str | None = Query(default=None),
):
    client_club_id: int | None = None

    if token is not None:
        try:
            with SessionLocal() as db:
                user = auth_service.get_user_from_token(db, token)
                if user is not None:
                    club = club_repository.get_by_user_id(db, user.id)
                    if club is not None:
                        client_club_id = club.id
        except Exception:
            # Token inválido o expirado: se permite la conexión en modo espectador
            client_club_id = None

    # we use the connection manager to connect the WS to the match
    await match_connection_manager.connect(
        match_id=match_id,
        websocket=websocket,
        client_club_id=client_club_id,
    )

    # the try keeps the connection waiting while it's open (in the coroutine);
    # when the client closes it, receive_text() causes WebSocketDisconnect and the Manager runs disconnect
    try:
        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        match_connection_manager.disconnect(match_id, websocket)