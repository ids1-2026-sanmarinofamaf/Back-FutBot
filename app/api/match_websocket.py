from fastapi import (APIRouter, WebSocket, WebSocketDisconnect)

from app.services.match_websocket_service import (match_connection_manager)

# APIRouter is used to define the routes of this module separately and then add them to the main application.
router = APIRouter()


@router.websocket("/ws/matches/{match_id}")
async def match_websocket(websocket: WebSocket, match_id: int):
    # we use the connection manager to connect the WS to the match
    await match_connection_manager.connect(match_id, websocket)

    # the try keeps the connection waiting while it's open (in the coroutine);
    # when the client closes it, receive_text() causes WebSocketDisconnect and the Manager runs disconnect
    try:
        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        match_connection_manager.disconnect(match_id, websocket)