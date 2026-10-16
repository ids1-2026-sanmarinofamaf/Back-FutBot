from fastapi import WebSocket

class LeagueConnectionManager:

    def __init__(self):
        # league_id -> websocket connections
        self.active_connections: dict[int, list[WebSocket]] = {}

    
    async def connect(
        self,
        league_id: int,
        websocket: WebSocket,
    ) -> None:
        # accept and register a new WebSocket connection
        await websocket.accept()

        if league_id not in self.active_connections:
            self.active_connections[league_id] = []

        self.active_connections[league_id].append(websocket)

    def disconnect(
        self,
        league_id: int,
        websocket: WebSocket,
    ) -> None:
        # remove a WebSocket connection from its league
        connections = self.active_connections.get(league_id)

        if connections is None:
            return

        if websocket in connections:
            connections.remove(websocket)

        if not connections:
            self.active_connections.pop(league_id, None)

    async def close_lobby(
        self,
        league_id: int,
        code: int = 1000,
        reason: str = "Lobby closed",
    ) -> None:
        # close all WebSocket connections associated with a league
        connections = list(
            self.active_connections.get(league_id, [])
        )

        for websocket in connections:
            try:
                await websocket.close(
                    code=code,
                    reason=reason,
                )
            except Exception:
                pass

        self.active_connections.pop(league_id, None)

    # send the current lobby state to a specific connection (used when a user join to a new league)
    async def send_state(
        self,
        websocket: WebSocket,
        state,
    ) -> None:
        await websocket.send_json(state.model_dump())

    # send a message to all connections in a specific league (used to broadcast events)
    async def broadcast(
        self,
        league_id: int,
        state,
    ) -> None:

        connections = list(
            self.active_connections.get(league_id, [])
        )

        disconnected = []

        for websocket in connections:
            try:
                await websocket.send_json(state.model_dump())
            except Exception:
                disconnected.append(websocket)

        for websocket in disconnected:
            self.disconnect(league_id, websocket)

# shared instance used to manage all league WebSocket connections
league_connection_manager = LeagueConnectionManager()
