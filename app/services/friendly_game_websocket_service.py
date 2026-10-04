from fastapi import WebSocket

from app.models.friendly_game import FriendlyGame

from app.schemas.friendly_game_websocket import (
    FriendlyGameLobbyState,
    FriendlyGameLobbyUser,
)


class FriendlyGameConnectionManager:

    def __init__(self):
        # friendly_game_id -> ws connections
        self.active_connections: dict[int, list[WebSocket]] = {}

    async def connect(
        self,
        friendly_game_id: int,
        websocket: WebSocket,
    ) -> None:

        await websocket.accept()

        if friendly_game_id not in self.active_connections:
            self.active_connections[friendly_game_id] = []

        self.active_connections[friendly_game_id].append(websocket)

    def disconnect(
        self,
        friendly_game_id: int,
        websocket: WebSocket,
    ) -> None:

        connections = self.active_connections.get(friendly_game_id)

        if connections is None:
            return

        if websocket in connections:
            connections.remove(websocket)

        if not connections:
            self.active_connections.pop(
                friendly_game_id,
                None,
            )

    async def send_state(
        self,
        websocket: WebSocket,
        state: FriendlyGameLobbyState,
    ) -> None:

        await websocket.send_json(state.model_dump())

    async def broadcast(
        self,
        friendly_game_id: int,
        state: FriendlyGameLobbyState,
    ) -> None:

        # copy the list of connections,
        # since the list can be modified while we are awaiting
        connections = list(
            self.active_connections.get(
                friendly_game_id,
                [],
            )
        )

        disconnected = []

        for websocket in connections:
            try:
                await websocket.send_json(state.model_dump())

            except Exception:
                disconnected.append(websocket)

        for websocket in disconnected:
            self.disconnect(
                friendly_game_id,
                websocket,
            )

    async def close_lobby(
        self,
        friendly_game_id: int,
        code: int = 1000,
        reason: str = "Lobby closed",
    ) -> None:

        connections = list(
            self.active_connections.get(
                friendly_game_id,
                [],
            )
        )

        for websocket in connections:
            try:
                await websocket.close(
                    code=code,
                    reason=reason,
                )
            except Exception:
                pass

        self.active_connections.pop(
            friendly_game_id,
            None,
        )


def build_friendly_game_lobby_state(
    friendly_game: FriendlyGame,
    match_id: int | None = None,
) -> FriendlyGameLobbyState:

    users = [
        FriendlyGameLobbyUser(
            user_name=participation.club.name,
            avatar=participation.club.avatar,
        )
        for participation in friendly_game.participations
    ]

    return FriendlyGameLobbyState(
        friendly_game_id=friendly_game.id,
        state=friendly_game.state.value,
        current_users=len(users),
        match_id=match_id,
        users=users,
    )


friendly_game_connection_manager = (FriendlyGameConnectionManager())