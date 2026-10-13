
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock

from app.main import app
from app.services.match_websocket_service import (
    MatchConnectionManager,
    match_connection_manager,
)
from app.schemas.match_websocket import (
    MatchStateMessage,
    BallState,
)


client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_match_connections():
    match_connection_manager.active_connections.clear()

    yield

    match_connection_manager.active_connections.clear()


def test_spectator_can_connect_without_participation():
    match_id = 100

    # The match websocket does not require a participation.
    with client.websocket_connect(
        f"/ws/matches/{match_id}"
    ):
        assert match_id in (
            match_connection_manager.active_connections
        )

        assert len(
            match_connection_manager.active_connections[match_id]
        ) == 1


def test_spectator_can_disconnect_and_reconnect():
    match_id = 101

    with client.websocket_connect(
        f"/ws/matches/{match_id}"
    ):
        assert len(
            match_connection_manager.active_connections[match_id]
        ) == 1

    # The first connection has been removed.
    assert match_id not in (
        match_connection_manager.active_connections
    )

    # Reconnect to the same match.
    with client.websocket_connect(
        f"/ws/matches/{match_id}"
    ):
        assert len(
            match_connection_manager.active_connections[match_id]
        ) == 1


def test_participant_can_reconnect_without_new_participation():
    match_id = 102

    # A participant uses the same websocket as a spectator.
    with client.websocket_connect(
        f"/ws/matches/{match_id}"
    ):
        assert len(
            match_connection_manager.active_connections[match_id]
        ) == 1

    assert match_id not in (
        match_connection_manager.active_connections
    )

    # Reconnecting does not invoke the REST join endpoint.
    with client.websocket_connect(
        f"/ws/matches/{match_id}"
    ):
        assert len(
            match_connection_manager.active_connections[match_id]
        ) == 1


def test_disconnect_does_not_affect_other_connections():
    match_id = 103

    with client.websocket_connect(
        f"/ws/matches/{match_id}"
    ):
        with client.websocket_connect(
            f"/ws/matches/{match_id}"
        ):
            assert len(
                match_connection_manager.active_connections[match_id]
            ) == 2

        # The second user left, but the first remains.
        assert len(
            match_connection_manager.active_connections[match_id]
        ) == 1

    assert match_id not in (
        match_connection_manager.active_connections
    )


@pytest.mark.asyncio
async def test_remaining_spectator_receives_match_updates():
    manager = MatchConnectionManager()
    match_id = 104

    participant_ws = AsyncMock()
    spectator_ws = AsyncMock()

    await manager.connect(match_id, participant_ws)
    await manager.connect(match_id, spectator_ws)

    # Participant leaves the visualization.
    manager.disconnect(match_id, participant_ws)

    message = MatchStateMessage(
        event="estado_partido",
        actual_tic=5,
        total_tic=100,
        user1_goals=1,
        user2_goals=0,
        ball=BallState(
            x=20.0,
            y=10.0,
            speed_x=0.0,
            speed_y=0.0,
        ),
        players=[],
    )

    # The backend broadcasts another tick.
    await manager.broadcast(match_id, message)

    spectator_ws.send_json.assert_awaited_once_with(
        message.model_dump()
    )

    participant_ws.send_json.assert_not_awaited()

    assert manager.active_connections[match_id] == [
        spectator_ws
    ]
