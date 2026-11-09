import asyncio

from app.game import penalty_session as penalty_session_module
from app.game.penalties import PenaltyShootout, PenaltySide
from app.game.penalty_session import PenaltySession
from app.services import match_websocket_service as ws_service


from fastapi.testclient import TestClient
import pytest
from unittest.mock import AsyncMock, Mock
import copy
from app.game.models.match_participation import MatchParticipation
from app.game.models.ball import Ball
from app.game.models.match import Match
from app.game.active_matches import register_match, remove_match
from app.schemas.match_websocket import (
    MatchStateMessage,
    MatchPlayerState,
    BallState,
    MatchCoachChange,
    MatchCoachChangesMessage,
    MatchCoachSubstitution,
    MatchCoachSubstitutionsMessage,
)
from app.main import app
# the endpoint always use the manager = match_connection_manager
from app.services.match_websocket_service import match_connection_manager
from app.services.match_websocket_service import (
    MatchConnectionManager,
    build_match_state_message,
    filter_coach_changes_for_client,
    filter_match_state_for_client,
)

from unittest.mock import AsyncMock, MagicMock

from app.game.match_runner import (
    MatchRunner,
    BehaviorCoordinatorProtocol,
    GameEngineProtocol,
)

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
        duration_ticks=4,
    )


@pytest.fixture
def active_match(match):
    register_match(match)
    yield match
    remove_match(match.match_id)

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

        if i < len(snapshot.players_a):
            assert sent_player.team == "A"
        else:
            assert sent_player.team == "B"


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

@pytest.mark.asyncio
async def test_broadcast_continues_if_one_websocket_fails():
    manager = MatchConnectionManager()

    broken_ws = AsyncMock()
    working_ws = AsyncMock()

    # simulate a disconnected/broken websocket
    broken_ws.send_json.side_effect = RuntimeError("connection lost")

    manager.active_connections[1] = [
        broken_ws,
        working_ws,
    ]

    message = MatchStateMessage(
        event="estado_partido",
        actual_tic=0,
        total_tic=10,
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

    await manager.broadcast(1, message)

    # even if the first websocket fails,
    # the message must still be sent to the other connection
    working_ws.send_json.assert_awaited_once_with(
        message.model_dump()
    )

    # the broken websocket should be removed
    assert broken_ws not in manager.active_connections[1]

@pytest.mark.asyncio
async def test_match_runner_sends_initial_state_and_tick_updates(match):
    behavior_coordinator = MagicMock(
        spec=BehaviorCoordinatorProtocol
    )

    behavior_coordinator.get_actions.return_value = ["wait"] * 6

    game_engine = MagicMock(
        spec=GameEngineProtocol
    )

    runner = MatchRunner(
        behavior_coordinator,
        game_engine,
        hydration_duration=0,
        halftime_duration=0,
        execution_window=0,
    )

    websocket = AsyncMock()

    match_connection_manager.active_connections.clear()
    match_connection_manager.active_connections[
        match.match_id
    ] = [websocket]

    # use only two ticks 
    match.duration_ticks = 4

    await runner.run_match(match)

    # 1 initial state + 4 tick updates + 3 break states + 9 break events
    assert websocket.send_json.await_count == 17

    sent_messages = [
        call.args[0]
        for call in websocket.send_json.await_args_list
    ]

    events = [message["event"] for message in sent_messages]

    assert events.count("estado_partido") == 8
    assert events.count("pause_started") == 3
    assert events.count("substitution_window_closed") == 3
    assert events.count("pause_finished") == 3

    assert sent_messages[0]["event"] == "estado_partido"
    assert sent_messages[0]["actual_tic"] == 0

    state_messages = [
        message
        for message in sent_messages
        if message["event"] == "estado_partido"
    ]

    assert [message["actual_tic"] for message in state_messages] == [
        0, 1, 1, 2, 2, 3, 3, 4
    ]


@pytest.mark.asyncio
async def test_close_match_continues_after_connection_error():
    manager = MatchConnectionManager()
    failing_connection = Mock()
    healthy_connection = Mock()

    failing_connection.close = AsyncMock(
        side_effect=RuntimeError("Connection already closed"),
    )
    healthy_connection.close = AsyncMock()

    manager.active_connections[123] = [
        failing_connection,
        healthy_connection,
    ]

    await manager.close_match_connection(123)

    failing_connection.close.assert_awaited_once_with()
    healthy_connection.close.assert_awaited_once_with()
    assert 123 not in manager.active_connections


@pytest.mark.asyncio
async def test_connect_sends_match_info_and_initial_state_when_match_active(active_match):
    manager = MatchConnectionManager()
    websocket = AsyncMock()

    await manager.connect(active_match.match_id, websocket, client_club_id=1)

    websocket.accept.assert_awaited_once()
    assert manager.connection_clubs[websocket] == 1
    assert websocket.send_json.await_count == 2

    sent_info = websocket.send_json.await_args_list[0].args[0]
    assert sent_info["event"] == "match_info"
    assert sent_info["match_id"] == active_match.match_id
    assert sent_info["my_club_id"] == 1
    assert sent_info["team_a"]["club_id"] == active_match.participation_a.club_id
    assert sent_info["team_b"]["club_id"] == active_match.participation_b.club_id
    assert len(sent_info["players"]) == 12

    sent_state = websocket.send_json.await_args_list[1].args[0]
    assert sent_state["event"] == "estado_partido"
    assert sent_state["actual_tic"] == 0


@pytest.mark.asyncio
async def test_connect_as_spectator_sends_match_info_with_none_club(active_match):
    manager = MatchConnectionManager()
    websocket = AsyncMock()

    await manager.connect(active_match.match_id, websocket, client_club_id=None)

    websocket.accept.assert_awaited_once()
    assert manager.connection_clubs[websocket] is None
    assert websocket.send_json.await_count == 2

    sent_info = websocket.send_json.await_args_list[0].args[0]
    assert sent_info["event"] == "match_info"
    assert sent_info["my_club_id"] is None


def test_disconnect_cleans_connection_clubs():
    manager = MatchConnectionManager()
    ws = AsyncMock()
    manager.active_connections[1] = [ws]
    manager.connection_clubs[ws] = 1

    manager.disconnect(1, ws)

    assert ws not in manager.connection_clubs
    assert 1 not in manager.active_connections


def test_websocket_endpoint_with_valid_token(active_match, monkeypatch):
    match_connection_manager.active_connections.clear()
    match_connection_manager.connection_clubs.clear()

    for p in active_match.participation_a.players:
        if p.is_on_field:
            p.current_behavior_name = "Táctica A"
    for p in active_match.participation_b.players:
        if p.is_on_field:
            p.current_behavior_name = "Táctica B"

    monkeypatch.setattr("app.services.auth_service.get_user_from_token", lambda db, token: Mock(id=10))
    monkeypatch.setattr("app.repositories.club_repository.get_by_user_id", lambda db, user_id: Mock(id=1))

    with client.websocket_connect(f"/ws/matches/{active_match.match_id}?token=valid_token") as ws:
        msg1 = ws.receive_json()
        assert msg1["event"] == "match_info"
        assert msg1["my_club_id"] == 1

        msg2 = ws.receive_json()
        assert msg2["event"] == "estado_partido"
        assert msg2["actual_tic"] == 0

        # Privacidad táctica: el club 1 solo ve comportamientos del equipo A
        starters_a = [p for p in msg2["players"] if p["team"] == "A" and p["is_on_field"]]
        players_b = [p for p in msg2["players"] if p["team"] == "B"]
        assert all(p["current_behavior_name"] == "Táctica A" for p in starters_a)
        assert all(p["current_behavior_id"] is not None for p in starters_a)
        assert all(p["current_behavior_name"] is None for p in players_b)
        assert all(p["current_behavior_id"] is None for p in players_b)

    match_connection_manager.active_connections.clear()
    match_connection_manager.connection_clubs.clear()


def test_websocket_endpoint_spectator_without_token(active_match):
    match_connection_manager.active_connections.clear()
    match_connection_manager.connection_clubs.clear()

    with client.websocket_connect(f"/ws/matches/{active_match.match_id}") as ws:
        msg1 = ws.receive_json()
        assert msg1["event"] == "match_info"
        assert msg1["my_club_id"] is None

        msg2 = ws.receive_json()
        assert msg2["event"] == "estado_partido"

        # Privacidad táctica: espectadores no ven comportamientos de ningún equipo
        assert all(p["current_behavior_name"] is None for p in msg2["players"])
        assert all(p["current_behavior_id"] is None for p in msg2["players"])

    match_connection_manager.active_connections.clear()
    match_connection_manager.connection_clubs.clear()


def test_websocket_endpoint_with_invalid_token_falls_back_to_spectator(active_match, monkeypatch):
    match_connection_manager.active_connections.clear()
    match_connection_manager.connection_clubs.clear()

    monkeypatch.setattr(
        "app.services.auth_service.get_user_from_token",
        Mock(side_effect=Exception("Invalid token")),
    )

    with client.websocket_connect(f"/ws/matches/{active_match.match_id}?token=invalid_token") as ws:
        msg1 = ws.receive_json()
        assert msg1["event"] == "match_info"
        assert msg1["my_club_id"] is None

        msg2 = ws.receive_json()
        assert msg2["event"] == "estado_partido"

    match_connection_manager.active_connections.clear()
    match_connection_manager.connection_clubs.clear()


def test_filter_match_state_for_client_privacy():
    message = MatchStateMessage(
        event="estado_partido",
        actual_tic=10,
        total_tic=100,
        user1_goals=0,
        user2_goals=0,
        ball=BallState(x=20.0, y=10.0, speed_x=0.0, speed_y=0.0),
        players=[
            MatchPlayerState(
                player_id=1,
                x=5.0,
                y=5.0,
                is_on_field=True,
                team="A",
                current_behavior_id=10,
                current_behavior_name="Ataque",
            ),
            MatchPlayerState(
                player_id=7,
                x=15.0,
                y=5.0,
                is_on_field=True,
                team="B",
                current_behavior_id=20,
                current_behavior_name="Defensa",
            ),
        ],
    )

    # Cliente del club A (club_id=1)
    filtered_a = filter_match_state_for_client(
        message, client_club_id=1, club_a_id=1, club_b_id=2
    )
    assert filtered_a.players[0].current_behavior_name == "Ataque"
    assert filtered_a.players[0].current_behavior_id == 10
    assert filtered_a.players[1].current_behavior_name is None
    assert filtered_a.players[1].current_behavior_id is None

    # Cliente del club B (club_id=2)
    filtered_b = filter_match_state_for_client(
        message, client_club_id=2, club_a_id=1, club_b_id=2
    )
    assert filtered_b.players[0].current_behavior_name is None
    assert filtered_b.players[0].current_behavior_id is None
    assert filtered_b.players[1].current_behavior_name == "Defensa"
    assert filtered_b.players[1].current_behavior_id == 20

    # Espectador (club_id=None)
    filtered_spectator = filter_match_state_for_client(
        message, client_club_id=None, club_a_id=1, club_b_id=2
    )
    assert filtered_spectator.players[0].current_behavior_name is None
    assert filtered_spectator.players[0].current_behavior_id is None
    assert filtered_spectator.players[1].current_behavior_name is None
    assert filtered_spectator.players[1].current_behavior_id is None


@pytest.mark.asyncio
async def test_broadcast_filters_tactical_info_per_client_club(active_match):
    manager = MatchConnectionManager()

    for p in active_match.participation_a.players:
        if p.is_on_field:
            p.current_behavior_name = "Táctica A"
    for p in active_match.participation_b.players:
        if p.is_on_field:
            p.current_behavior_name = "Táctica B"

    ws_a = AsyncMock()
    ws_b = AsyncMock()
    ws_spectator = AsyncMock()

    manager.active_connections[active_match.match_id] = [ws_a, ws_b, ws_spectator]
    manager.connection_clubs[ws_a] = 1  # club A
    manager.connection_clubs[ws_b] = 2  # club B
    manager.connection_clubs[ws_spectator] = None  # espectador

    snapshot = active_match.snapshot()
    message = build_match_state_message(snapshot)

    await manager.broadcast(active_match.match_id, message)

    # ws_a solo ve comportamientos del equipo A
    sent_a = ws_a.send_json.await_args.args[0]
    for p in sent_a["players"]:
        if p["team"] == "A" and p["is_on_field"]:
            assert p["current_behavior_name"] == "Táctica A"
            assert p["current_behavior_id"] is not None
        else:
            assert p["current_behavior_name"] is None
            assert p["current_behavior_id"] is None

    # ws_b solo ve comportamientos del equipo B
    sent_b = ws_b.send_json.await_args.args[0]
    for p in sent_b["players"]:
        if p["team"] == "B" and p["is_on_field"]:
            assert p["current_behavior_name"] == "Táctica B"
            assert p["current_behavior_id"] is not None
        else:
            assert p["current_behavior_name"] is None
            assert p["current_behavior_id"] is None

    # ws_spectator no ve comportamientos de ninguno
    sent_spec = ws_spectator.send_json.await_args.args[0]
    for p in sent_spec["players"]:
        assert p["current_behavior_name"] is None
        assert p["current_behavior_id"] is None



@pytest.fixture
def penalty_reconnection(active_match, monkeypatch):
    clock = Mock(return_value=100.0)
    monkeypatch.setattr(penalty_session_module, "monotonic", clock)
    monkeypatch.setattr(ws_service, "monotonic", clock)

    session = PenaltySession(
        shootout=PenaltyShootout(
            club_a_id=1,
            club_b_id=2,
            kickers_a=(1, 2, 3),
            kickers_b=(7, 8, 9),
            seed=active_match.match_id,
        ),
        response_timeout=10.0,
    )
    return session, clock




class InitialMessageBarrier:
    def __init__(self, blocked_event):
        self.blocked_event = blocked_event
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.messages = []

    async def send_json(self, payload):
        if payload["event"] == self.blocked_event:
            self.started.set()
            await self.release.wait()
        self.messages.append(payload)


@pytest.mark.asyncio
async def test_live_penalty_result_waits_for_initial_messages(
    active_match,
    penalty_reconnection,
):
    session, _ = penalty_reconnection
    active_match.penalty_session = session
    session.open_turn()

    barrier = InitialMessageBarrier("match_info")
    websocket = AsyncMock()
    websocket.send_json.side_effect = barrier.send_json
    manager = MatchConnectionManager()

    connect_task = asyncio.create_task(
        manager.connect(active_match.match_id, websocket),
    )
    broadcast_task = None

    try:
        await asyncio.wait_for(barrier.started.wait(), timeout=1.0)

        # Simulate the runner resolving a penalty during initialization.
        result = session.shootout.resolve_penalty(
            PenaltySide.LEFT,
            PenaltySide.RIGHT,
        )
        session.accepting_choices = False

        broadcast_task = asyncio.create_task(
            manager.broadcast(
                active_match.match_id,
                ws_service.build_penalty_result_message(
                    result,
                    duration=5.0,
                ),
            ),
        )
        await asyncio.sleep(0)

        assert not broadcast_task.done()
        assert websocket.send_json.await_count == 1

        barrier.release.set()
        await asyncio.wait_for(
            asyncio.gather(connect_task, broadcast_task),
            timeout=1.0,
        )

        assert [message["event"] for message in barrier.messages] == [
            "match_info",
            "estado_partido",
            "penalty_history",
            "penalty_result",
        ]
    finally:
        tasks = [connect_task]
        if broadcast_task is not None:
            tasks.append(broadcast_task)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "blocked_event",
    [
        "match_info",
        "estado_partido",
        "penalty_history",
        "penalty_turn_started",
    ],
)
async def test_initial_message_timeout_cleans_connection(
    active_match,
    penalty_reconnection,
    monkeypatch,
    blocked_event,
):
    session, _ = penalty_reconnection
    active_match.penalty_session = session
    session.open_turn()
    monkeypatch.setattr(ws_service, "SEND_TIMEOUT_SECONDS", 0.01)

    barrier = InitialMessageBarrier(blocked_event)
    websocket = AsyncMock()
    websocket.send_json.side_effect = barrier.send_json
    manager = MatchConnectionManager()

    with pytest.raises(TimeoutError):
        await asyncio.wait_for(
            manager.connect(active_match.match_id, websocket),
            timeout=1.0,
        )

    assert barrier.started.is_set()
    assert active_match.match_id not in manager.active_connections
    assert websocket not in manager.connection_clubs
    assert websocket not in manager._send_locks
    websocket.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_initial_message_cancellation_cleans_connection(active_match):
    barrier = InitialMessageBarrier("match_info")
    websocket = AsyncMock()
    websocket.send_json.side_effect = barrier.send_json
    manager = MatchConnectionManager()

    task = asyncio.create_task(
        manager.connect(active_match.match_id, websocket),
    )

    try:
        await asyncio.wait_for(barrier.started.wait(), timeout=1.0)
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    assert active_match.match_id not in manager.active_connections
    assert websocket not in manager.connection_clubs
    assert websocket not in manager._send_locks
    websocket.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_reconnection_waits_for_match_winner_confirmation(
    active_match,
    penalty_reconnection,
):
    session, _ = penalty_reconnection
    active_match.penalty_session = session

    for _ in range(6):
        session.shootout.resolve_penalty(
            PenaltySide.LEFT,
            PenaltySide.LEFT,
        )

    assert session.shootout.winner_club_id is not None
    assert active_match.winner_club_id is None

    manager = MatchConnectionManager()
    during_pause = AsyncMock()

    await manager.connect(
        active_match.match_id,
        during_pause,
        client_club_id=1,
    )

    messages = [
        awaited.args[0]
        for awaited in during_pause.send_json.await_args_list
    ]

    # The last pause has not ended, so no winner is announced yet.
    assert [message["event"] for message in messages] == [
        "match_info",
        "estado_partido",
        "penalty_history",
    ]
    assert len(messages[2]["results"]) == 6

    # Simulate the runner confirming the winner after the final pause.
    active_match.winner_club_id = session.shootout.winner_club_id

    after_pause = AsyncMock()
    await manager.connect(
        active_match.match_id,
        after_pause,
        client_club_id=1,
    )

    messages = [
        awaited.args[0]
        for awaited in after_pause.send_json.await_args_list
    ]

    assert [message["event"] for message in messages] == [
        "match_info",
        "estado_partido",
        "penalty_history",
        "penalty_shootout_finished",
    ]
    assert len(messages[2]["results"]) == 6


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["none", "open", "between", "finished"])
@pytest.mark.parametrize("client_club_id", [1, None])
async def test_connect_restores_existing_penalty_messages(
    active_match,
    penalty_reconnection,
    phase,
    client_club_id,
):
    session, clock = penalty_reconnection

    if phase != "none":
        active_match.penalty_session = session

    if phase == "open":
        for _ in range(2):
            session.shootout.resolve_penalty(
                PenaltySide.LEFT,
                PenaltySide.RIGHT,
            )

        session.open_turn()
        session.submit_choice(1, 3, PenaltySide.CENTER)
        clock.return_value = 104.0

    elif phase == "between":
        session.shootout.resolve_penalty(
            PenaltySide.LEFT,
            PenaltySide.RIGHT,
        )

    elif phase == "finished":
        for _ in range(6):
            session.shootout.resolve_penalty(
                PenaltySide.LEFT,
                PenaltySide.LEFT,
            )

        active_match.winner_club_id = session.shootout.winner_club_id

    manager = MatchConnectionManager()
    websocket = AsyncMock()

    await manager.connect(
        active_match.match_id,
        websocket,
        client_club_id=client_club_id,
    )

    messages = [
        awaited.args[0]
        for awaited in websocket.send_json.await_args_list
    ]

    assert [message["event"] for message in messages[:2]] == [
        "match_info",
        "estado_partido",
    ]

    if phase == "none":
        assert len(messages) == 2
        return

    assert messages[2] == {
        "event": "penalty_history",
        "results": [
            {
                **result,
                "event": "penalty_result",
                "duration": 0,
            }
            for result in session.shootout.results
        ],
    }

    if phase == "open":
        assert len(messages) == 4
        assert messages[3] == {
            "event": "penalty_turn_started",
            "turn": 3,
            "club_id": 1,
            "kicker": 2,
            "score_club_a": 1,
            "score_club_b": 1,
            "remaining_seconds": 6.0,
        }
        assert session.choices == {1: PenaltySide.CENTER}

    elif phase == "finished":
        assert len(messages) == 4
        assert messages[3] == {
            "event": "penalty_shootout_finished",
            "winner_club_id": session.shootout.winner_club_id,
            "score_club_a": 0,
            "score_club_b": 0,
        }

    else:
        assert len(messages) == 3

    assert all("choices" not in message for message in messages)


@pytest.mark.asyncio
async def test_broadcast_filters_pending_substitution_per_client_club(active_match):
    manager = MatchConnectionManager()

    active_match.participation_a.plan_substitution(
        player_out_id=1,
        player_in_id=4,
        period=active_match.current_period,
        from_coach=True,
    )

    ws_a = AsyncMock()
    ws_b = AsyncMock()
    ws_spectator = AsyncMock()

    manager.active_connections[active_match.match_id] = [ws_a, ws_b, ws_spectator]
    manager.connection_clubs[ws_a] = 1
    manager.connection_clubs[ws_b] = 2
    manager.connection_clubs[ws_spectator] = None

    snapshot = active_match.snapshot()
    message = build_match_state_message(snapshot)

    await manager.broadcast(active_match.match_id, message)

    sent_a = ws_a.send_json.await_args.args[0]
    sent_b = ws_b.send_json.await_args.args[0]
    sent_spec = ws_spectator.send_json.await_args.args[0]

    assert sent_a["pending_substitution"] == {"player_out_id": 1, "player_in_id": 4}
    assert sent_b["pending_substitution"] is None
    assert sent_spec["pending_substitution"] is None


# coach (DT) events privacy

def _coach_changes_message():
    return MatchCoachChangesMessage(
        from_tic=5,
        changes=[
            MatchCoachChange(club_id=1, player_id=10, behavior="Attacker"),
            MatchCoachChange(club_id=2, player_id=20, behavior="Defender"),
            MatchCoachChange(club_id=1, player_id=11, behavior="Defender"),
        ],
    )


def _manager_with_clients(match_id, clubs):
    manager = MatchConnectionManager()
    sockets = []

    for club_id in clubs:
        websocket = AsyncMock()
        manager.connection_clubs[websocket] = club_id
        sockets.append(websocket)

    manager.active_connections[match_id] = list(sockets)

    return manager, sockets


def test_filter_coach_changes_keeps_only_own_club():
    filtered = filter_coach_changes_for_client(
        _coach_changes_message(),
        client_club_id=1,
    )

    assert filtered.from_tic == 5
    assert [(c.club_id, c.player_id) for c in filtered.changes] == [(1, 10), (1, 11)]


@pytest.mark.parametrize("client_club_id", [None, 3])
def test_filter_coach_changes_returns_none_without_own_changes(client_club_id):
    assert filter_coach_changes_for_client(
        _coach_changes_message(),
        client_club_id=client_club_id,
    ) is None


@pytest.mark.asyncio
async def test_broadcast_coach_changes_only_reaches_their_own_club():
    manager, (ws_a, ws_b, ws_spectator) = _manager_with_clients(1, [1, 2, None])

    await manager.broadcast(1, _coach_changes_message())

    sent_a = ws_a.send_json.await_args.args[0]
    sent_b = ws_b.send_json.await_args.args[0]

    assert {change["club_id"] for change in sent_a["changes"]} == {1}
    assert len(sent_a["changes"]) == 2
    assert sent_b["changes"] == [
        {"club_id": 2, "player_id": 20, "behavior": "Defender"},
    ]
    ws_spectator.send_json.assert_not_awaited()


@pytest.mark.asyncio
async def test_broadcast_coach_changes_skips_club_without_changes():
    manager, (ws_a, ws_b) = _manager_with_clients(1, [1, 2])
    message = MatchCoachChangesMessage(
        from_tic=5,
        changes=[MatchCoachChange(club_id=1, player_id=10, behavior="Attacker")],
    )

    await manager.broadcast(1, message)

    ws_a.send_json.assert_awaited_once()
    ws_b.send_json.assert_not_awaited()


@pytest.mark.asyncio
async def test_broadcast_coach_substitutions_reaches_everyone():
    # substitutions reveal no behavior and are visible in estado_partido anyway
    manager, sockets = _manager_with_clients(1, [1, 2, None])
    message = MatchCoachSubstitutionsMessage(
        changes=[MatchCoachSubstitution(club_id=1, player_out_id=10, player_in_id=13)],
    )

    await manager.broadcast(1, message)

    for websocket in sockets:
        websocket.send_json.assert_awaited_once_with(message.model_dump())
