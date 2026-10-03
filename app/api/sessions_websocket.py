from typing import Annotated

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from app.api.deps import get_current_user_ws
from app.core.ws_manager import manager
from app.models.user import User

router = APIRouter(tags=["sessions"])

# Websocket de inicio de sesion
@router.websocket("/ws/sessions")
async def websocket_endpoint(
    websocket: WebSocket,
    user: Annotated[User, Depends(get_current_user_ws)]
):
    await manager.connect(user.id, websocket)
    try:
        await websocket.send_text("Bienvenido")
        while True:
            # El cliente no manda nada útil; esperamos para detectar cuándo se desconecta
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(user.id, websocket)