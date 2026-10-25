from uuid import UUID

from fastapi import WebSocket

from app.schemas.match_websocket import MatchStateMessage
from app.schemas.behavior_preview import BehaviorPreviewFinishedMessage

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
        connections = self.active_connections.get(preview_id, [])

        disconnected = []

        for websocket in connections:
            try:
                await websocket.send_json(message.model_dump())
            except Exception:
                disconnected.append(websocket)

        for websocket in disconnected:
            self.disconnect(preview_id, websocket)


    async def close_preview_connection(
        self,
        preview_id: UUID,
    ) -> None:
        connections = self.active_connections.pop(preview_id, [])

        for websocket in connections:
            try:
                await websocket.close()
            except Exception:
                pass

preview_connection_manager = PreviewConnectionManager()
        