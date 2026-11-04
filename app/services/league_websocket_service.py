import asyncio

from typing import Literal

from fastapi import WebSocket

from app.models.league import League
from app.models.club import Club
from app.schemas.league import LeagueStartedEvent
from app.schemas.league_websocket import (
    LeagueLobbyState,
    LeagueLobbyUser,
    LeagueUserEvent,
    LeagueStateEvent,
)


SEND_TIMEOUT_SECONDS = 5


class LeagueConnectionManager:

    def __init__(self):
        # league_id -> user_id -> websocket connections
        self.active_connections: dict[int, dict[int, set[WebSocket]]] = {}
        self._send_locks: dict[WebSocket, asyncio.Lock] = {}
        self._ready_events: dict[WebSocket, asyncio.Event] = {} 

    # accept and register a new WebSocket connection
    async def connect(
        self,
        league_id: int,
        user_id: int,
        websocket: WebSocket,
        initializing: bool = False,
    ) -> None:
        await websocket.accept()

        self._send_locks[websocket] = asyncio.Lock()

        event = asyncio.Event()

        if not initializing:
            event.set()

        self._ready_events[websocket] = event

        league_connections = self.active_connections.setdefault(
            league_id, {}
        )

        league_connections.setdefault(user_id, set()).add(websocket)

     # remove a WebSocket connection from its league
    def disconnect(
        self,
        league_id: int,
        user_id: int,
        websocket: WebSocket,
    ) -> None:
        event = self._ready_events.pop(websocket, None)
        self._send_locks.pop(websocket, None)

        if event is not None:
            event.set()

        league_connections = self.active_connections.get(league_id)

        if league_connections is None:
            return

        user_connections = league_connections.get(user_id)

        if user_connections is None:
            return

        user_connections.discard(websocket)

        if not user_connections:
            league_connections.pop(user_id, None)

        if not league_connections:
            self.active_connections.pop(league_id, None)


    async def disconnect_user(
        self,
        league_id: int,
        user_id: int,
    ) -> None:
        league_connections = self.active_connections.get(league_id)

        if league_connections is None:
            return

        connections = list(league_connections.pop(user_id, set()))

        if not league_connections:
            self.active_connections.pop(league_id, None)

        connections_with_locks = [
            (websocket, self._send_locks.pop(websocket, None))
            for websocket in connections
        ]

        for websocket in connections:
            event = self._ready_events.pop(websocket, None)

            if event is not None:
                event.set()

        for websocket, lock in connections_with_locks:
            try:
                await self._close_connection(
                    websocket=websocket,
                    lock=lock,
                    code=4403,
                    reason="User left the league",
                )
                
            except Exception:
                pass

    # close all WebSocket connections associated with a league
    async def close_lobby(
        self,
        league_id: int,
        code: int = 1000,
        reason: str = "Lobby closed",
    ) -> None:
        league_connections = self.active_connections.pop(
            league_id, {}
        )

        connections = [
            websocket
            for user_connections in league_connections.values()
            for websocket in user_connections
        ]

        connections_with_locks = [
            (websocket, self._send_locks.pop(websocket, None))
            for websocket in connections
        ]

        for websocket in connections:
            event = self._ready_events.pop(websocket, None)

            if event is not None:
                event.set()

        for websocket, lock in connections_with_locks:
            try:
                await self._close_connection(
                    websocket=websocket,
                    lock=lock,
                    code=code,
                    reason=reason,
                )
            except Exception:
                pass


    async def send_initial_states(
        self,
        websocket: WebSocket,
        lobby_state: LeagueLobbyState,
        league_state: LeagueStateEvent,
    ) -> None:
        event = self._ready_events.get(websocket, None)

        if event is None:
            raise RuntimeError("WebSocket is not registered")

        async with asyncio.timeout(SEND_TIMEOUT_SECONDS):
            await self.send_state(
                websocket,
                lobby_state,
            )

            await self.send_state(
                websocket,
                league_state,
            )

            if self._ready_events.get(websocket) is not event:
                raise RuntimeError("WebSocket is no longer registered")

            event.set()


    # send the current lobby state to a specific connection (used when a user join to a new league)
    async def send_state(
        self,
        websocket: WebSocket,
        state: LeagueLobbyState | LeagueStateEvent,
    ) -> None:
        await self._send_json(
            websocket,
            state.model_dump(mode="json"),
            )

    # send a message to all connections in a specific league (used to broadcast events)
    async def broadcast(
        self,
        league_id: int,
        state: LeagueLobbyState | LeagueUserEvent | LeagueStartedEvent,
    ) -> None:
        league_connections = self.active_connections.get(
            league_id, {}
        )

        # Copy connections to avoid changes during await
        connections = [
            (user_id, websocket)
            for user_id, user_connections in league_connections.items()
            for websocket in user_connections
        ]

        payload = state.model_dump(mode="json")

        sends = [
            self._send_to_connection(
                league_id=league_id,
                user_id=user_id,
                websocket=websocket,
                payload=payload,
            )
            for user_id, websocket in connections
        ]

        await asyncio.gather(*sends)


    async def _send_json(
        self,
        websocket: WebSocket,
        payload: dict
    ) -> None:
        lock = self._send_locks.get(websocket)

        if lock is None:
            raise RuntimeError("WebSocket is not registered")

        async with asyncio.timeout(SEND_TIMEOUT_SECONDS):
            async with lock:
                if self._send_locks.get(websocket) is not lock:
                    raise RuntimeError("WebSocket is no longer registered")

                await websocket.send_json(payload)


    async def _close_connection(
        self,
        websocket: WebSocket,
        lock: asyncio.Lock | None,
        code: int,
        reason: str,
    ) -> None:
        if lock is None:
            return

        async with asyncio.timeout(SEND_TIMEOUT_SECONDS):
            async with lock:
                await websocket.close(
                    code=code,
                    reason=reason,
                )


    async def _send_to_connection(
        self,
        league_id: int,
        user_id: int,
        websocket: WebSocket,
        payload: dict,
    ) -> None:
        try:
            event = self._ready_events.get(websocket, None)

            if event is None:
                raise RuntimeError("WebSocket is not registered")
            
            async with asyncio.timeout(SEND_TIMEOUT_SECONDS):
                await event.wait()

                await self._send_json(
                    websocket=websocket,
                    payload=payload,
                )

        except Exception:
            self.disconnect(
                league_id,
                user_id,
                websocket,
            )


# build the list of clubs participating in the league
def build_league_lobby_state(
    league: League,
) -> LeagueLobbyState:
    users = [
        LeagueLobbyUser(
            club_id=participation.club_id,
            user_name=participation.club.name,
            avatar=participation.club.avatar,
            is_creator=(
                participation.club_id == league.creator_id
            ),
        )
        for participation in league.league_participations
    ]
    # the actual lobby state
    return LeagueLobbyState(
        league_id=league.id,
        state=league.state.value,
        current_users=len(users),
        users=users,
    )

# build an event when a club joins or leaves a league 
def build_league_user_event(
    league: League,
    club: Club,
    event_type: Literal["user_joined", "user_left"],
) -> LeagueUserEvent:
    
    return LeagueUserEvent(
        type=event_type,
        league_id=league.id,
        user=LeagueLobbyUser(
            club_id=club.id,
            user_name=club.name,
            avatar=club.avatar,
            is_creator=(club.id == league.creator_id),
        ),
    )


# shared instance used to manage all league WebSocket connections
league_connection_manager = LeagueConnectionManager()
