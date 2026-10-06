from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    WebSocket,
    status,
)

from sqlalchemy.orm import Session

from app.api.deps import get_current_user_ws
from app.core.ws_manager import manager
from app.database import get_db
from app.models.user import User
from app.services import session_websocket_service


router = APIRouter(
    tags=["sessions"]
)


@router.websocket("/ws/sessions")
async def websocket_endpoint(
    websocket: WebSocket,
    user: Annotated[
        User,
        Depends(get_current_user_ws),
    ],
    db: Annotated[
        Session,
        Depends(get_db),
    ],
):
    await manager.connect(
        user.id,
        websocket,
    )

    try:
        # El servidor manda inmediatamente el estado completo.
        await (
            session_websocket_service
            .send_friendly_games_to_connection(
                websocket=websocket,
                db=db,
            )
        )

        while True:
            event = await websocket.receive()

            if event["type"] == "websocket.disconnect":
                break

            # Este websocket es únicamente server -> client.
            # Si el cliente intenta enviar información,
            # se viola el contrato.
            if event["type"] == "websocket.receive":
                await websocket.close(
                    code=status.WS_1008_POLICY_VIOLATION
                )
                break

    finally:
        manager.disconnect(
            user.id,
            websocket,
        )