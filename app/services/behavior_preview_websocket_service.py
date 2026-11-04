import asyncio
import logging

from starlette.websockets import WebSocketDisconnect

from uuid import UUID

from fastapi import WebSocket

from app.schemas.match_websocket import MatchStateMessage
from app.schemas.behavior_preview import BehaviorPreviewFinishedMessage


SEND_TIMEOUT_SECONDS = 2
CLOSE_TIMEOUT_SECONDS = 2

logger = logging.getLogger(__name__)


class PreviewConnectionManager:
    def __init__(self):
        self.active_connections: dict[UUID, list[WebSocket]] = {}


    async def connect(
        self,
        preview_id: UUID,
        websocket: WebSocket,
    ) -> None:
        await websocket.accept()

        if preview_id not in self.active_connections:
            self.active_connections[preview_id] = []

        self.active_connections[preview_id].append(websocket)


    def disconnect(
        self,
        preview_id: UUID,
        websocket: WebSocket,
    ) -> None:
        connections = self.active_connections.get(preview_id, [])

        if not connections:
            return

        if websocket in connections:
            connections.remove(websocket)

        if not connections:
            self.active_connections.pop(preview_id, None)


    async def broadcast(
        self,
        preview_id: UUID,
        message: MatchStateMessage | BehaviorPreviewFinishedMessage,
    ) -> None:
        connections = tuple(
            self.active_connections.get(preview_id, [])
            )

        payload = message.model_dump(mode="json")

        for websocket in connections:
            try:
                async with asyncio.timeout(SEND_TIMEOUT_SECONDS):
                    await websocket.send_json(payload)

            except (
                TimeoutError,
                WebSocketDisconnect,
                OSError,
            ):
                self.disconnect(preview_id, websocket)
                await self._close_connection(websocket)

            except Exception:
                logger.exception(
                    "Unexpected error sending preview event: preview_id=%s",
                    preview_id,
                )
                self.disconnect(preview_id, websocket)
                await self._close_connection(websocket)


    async def _close_connection(
        self,
        websocket: WebSocket
    ) -> None:
        try:
            async with asyncio.timeout(CLOSE_TIMEOUT_SECONDS):
                await websocket.close()
        except (TimeoutError, WebSocketDisconnect, OSError):
            pass
        except Exception:
            logger.exception("Unexpected error closing preview WebSocket")


    async def close_preview_connection(
        self,
        preview_id: UUID,
    ) -> None:
        connections = self.active_connections.pop(preview_id, [])

        for websocket in connections:
            await self._close_connection(websocket)


preview_connection_manager = PreviewConnectionManager()
        