from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    WebSocket,
    WebSocketDisconnect,
    status,
)

from app.api.deps import get_current_user_ws
from app.models.user import User

from app.services.behavior_preview_service import (
    preview_belongs_to_user,
)
from app.services.behavior_preview_websocket_service import (
    preview_connection_manager,
)


router = APIRouter(
    tags=["Behavior Previews WebSocket"],
)


@router.websocket("/ws/behaviors/previews/{preview_id}")
async def behavior_preview_websocket(
    websocket: WebSocket,
    preview_id: UUID,
    user: User = Depends(get_current_user_ws),
):
    if not preview_belongs_to_user(
        preview_id=preview_id,
        user_id=user.id,
    ):
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
        )
        return

    await preview_connection_manager.connect(
        preview_id,
        websocket,
    )

    try:
        while True:
            event = await websocket.receive()

            if event["type"] == "websocket.disconnect":
                break

            if event["type"] == "websocket.receive":
                await websocket.close(
                    code=status.WS_1008_POLICY_VIOLATION,
                )
                break

    except WebSocketDisconnect:
        pass

    finally:
        preview_connection_manager.disconnect(
            preview_id,
            websocket,
        )