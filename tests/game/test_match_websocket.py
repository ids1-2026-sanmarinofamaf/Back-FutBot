from fastapi.testclient import TestClient
import pytest
from unittest.mock import AsyncMock
import copy
from app.game.models.match_participation import MatchParticipation
from app.game.models.ball import Ball
from app.game.models.match import Match
from app.schemas.match_websocket import (MatchStateMessage,BallState)
from app.main import app
# the endpoint always use the manager = match_connection_manager
from app.services.match_websocket_service import match_connection_manager
from app.services.match_websocket_service import (MatchConnectionManager, build_match_state_message)

# TestClient simulates a real client interacting with the FastAPI app
client = TestClient(app)

@pytest.fixture
def match(six_players):
    # create independent players for each team.
    players_a = copy.deepcopy(six_players)
    players_b = copy.deepcopy(six_players)

    # players from both teams must have different ids.
    for player in players_b:
        player.player_id += 6

    participation_a = MatchParticipation(
        club_id=1,
        roster_id=1,
        players=players_a,
    )

    participation_b = MatchParticipation(
        club_id=2,
        roster_id=2,
        players=players_b,
    )

    return Match(
        match_id=1,
        participation_a=participation_a,
        participation_b=participation_b,
        ball=Ball(
            position=(20.0, 10.0),
            velocity=(0.0, 0.0),
        ),
        duration_ticks=10,
    )

def test_client_can_connect_to_match():
    match_id = 1

    match_connection_manager.active_connections.clear()
    
    with client.websocket_connect(f"/ws/matches/{match_id}"):
        # we checked that the connection was created and that it was just one
        assert match_id in match_connection_manager.active_connections
        assert len(match_connection_manager.active_connections[match_id]) == 1

    # clean it again after the test to avoid affecting the manager
    match_connection_manager.active_connections.clear()


@pytest.mark.asyncio
async def test_broadcast_sends_estado_partido():
    manager = MatchConnectionManager()

    # we created two fake ws
    ws1 = AsyncMock()
    ws2 = AsyncMock()

    # we set them as active connections of the manager
    manager.active_connections[1] = [ws1,ws2]

    message = MatchStateMessage(
        event="estado_partido",
        actual_tic=10,
        total_tic=100,
        user1_goals=0,
        user2_goals=0,
        ball=BallState(
            x=20.0,
            y=10.0,
            speed_x=0.0,
            speed_y=0.0,
        ),
        players=[],
    )

    # execute the broadcast for the ws in manager
    await manager.broadcast(1, message)

    expected_message = message.model_dump()

    # we checked that the ws were called by send_json(message) only once
    ws1.send_json.assert_awaited_once_with(expected_message)
    ws2.send_json.assert_awaited_once_with(expected_message)


def test_estado_partido_contains_required_fields(match):
    snapshot = match.snapshot()

    # format the snapshot into a state message
    message = build_match_state_message(snapshot)

    assert message.event == "estado_partido"

    assert message.actual_tic == snapshot.current_tick
    assert message.total_tic == snapshot.duration_ticks

    assert message.user1_goals == snapshot.score_a
    assert message.user2_goals == snapshot.score_b

    assert message.ball.x == snapshot.ball.position[0]
    assert message.ball.y == snapshot.ball.position[1]

    assert message.ball.speed_x == snapshot.ball.velocity[0]
    assert message.ball.speed_y == snapshot.ball.velocity[1]

    expected_players = [*snapshot.players_a, *snapshot.players_b]

    assert len(message.players) == len(expected_players)

    for i in range(len(expected_players)):
        sent_player = message.players[i]
        expected_player = expected_players[i]
        
        assert sent_player.player_id == expected_player.player_id
        assert sent_player.x == expected_player.position[0]
        assert sent_player.y == expected_player.position[1]
        assert sent_player.is_on_field == expected_player.is_on_field


def test_estado_partido_reflects_updated_state(match):
    first_snapshot = match.snapshot()

    first_message = build_match_state_message(
        first_snapshot
    )

    # update the match state
    match.current_tick += 1
    match.ball.position = (50.0,20.0,)

    # take a new snapshot and prepare the second message
    second_snapshot = match.snapshot()
    second_message = build_match_state_message(second_snapshot)

    assert (second_message.actual_tic == first_message.actual_tic + 1)

    assert second_message.ball.x == 50.0
    assert second_message.ball.y == 20.0

@pytest.mark.asyncio
async def test_close_match_connection_closes_all_websockets():
    manager = MatchConnectionManager()
    match_id = 1
    ws1 = AsyncMock()
    ws2 = AsyncMock()

    manager.active_connections[match_id] = [ws1,ws2]

    # execute close match connections with the match_id
    await manager.close_match_connection(match_id)

    # we checked that the ws were called by close only once
    ws1.close.assert_awaited_once()
    ws2.close.assert_awaited_once()

    # we check that this match isn't in the connections after closing it
    assert (match_id not in manager.active_connections)

@pytest.mark.asyncio
async def test_connect_accepts_and_saves_websocket():
    manager = MatchConnectionManager()
    websocket = AsyncMock()

    await manager.connect(1, websocket)
    # we checked that the ws were called by accept only once
    websocket.accept.assert_awaited_once()
    assert manager.active_connections[1] == [websocket]

def test_disconnect_removes_websocket():
    manager = MatchConnectionManager()
    websocket = AsyncMock()

    manager.active_connections[1] = [websocket]

    manager.disconnect(1, websocket)
    # check if 1 is not more in the active_connections
    assert 1 not in manager.active_connections