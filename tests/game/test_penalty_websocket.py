import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from app.game import penalty_session as session_module
from app.game.penalties import PenaltyShootout, PenaltySide
from app.game.penalty_session import PenaltySession
from app.schemas.match_websocket import BallState, MatchStateMessage
from app.services import match_websocket_service as ws_service


@pytest.fixture
def clock(monkeypatch):
    clock = Mock(return_value=100.0)
    monkeypatch.setattr(session_module, "monotonic", clock)
    monkeypatch.setattr(ws_service, "monotonic", clock)
    return clock


@pytest.fixture
def session(clock):
    return PenaltySession(
        shootout=PenaltyShootout(
            club_a_id=10,
            club_b_id=20,
            kickers_a=(11, 12, 13),
            kickers_b=(21, 22, 23),
            seed=123,
        ),
        response_timeout=10.0,
    )


@pytest.fixture
def result_message(session):
    result = session.shootout.resolve_penalty(
        PenaltySide.LEFT,
        PenaltySide.RIGHT,
    )
    return ws_service.build_penalty_result_message(result)


async def block_socket(*args, **kwargs):
    await asyncio.Event().wait()


@pytest.mark.parametrize(
    "resolved_turns, club_id, kicker",
    [
        (0, 10, 11),
        (1, 20, 21),
        (4, 10, 13),
        (5, 20, 23),
    ],
)
def test_turn_message_contains_public_state_only(
    session,
    clock,
    resolved_turns,
    club_id,
    kicker,
):
    for _ in range(resolved_turns):
        session.shootout.resolve_penalty(
            PenaltySide.LEFT,
            PenaltySide.RIGHT,
        )

    session.open_turn()
    session.submit_choice(
        club_id=10,
        turn=resolved_turns + 1,
        side=PenaltySide.CENTER,
    )

    clock.return_value = 104.0

    message = ws_service.build_penalty_turn_started_message(session)

    assert message.model_dump(mode="json") == {
        "event": "penalty_turn_started",
        "turn": resolved_turns + 1,
        "club_id": club_id,
        "kicker": kicker,
        "score_club_a": (resolved_turns + 1) // 2,
        "score_club_b": resolved_turns // 2,
        "remaining_seconds": 6.0,
    }

    # Building public state must not modify the pending choice.
    assert session.choices == {10: PenaltySide.CENTER}
    assert session.shootout.turn == resolved_turns


def test_remaining_seconds_never_becomes_negative(session, clock):
    session.open_turn()
    clock.return_value = 111.0

    message = ws_service.build_penalty_turn_started_message(session)

    assert message.remaining_seconds == 0.0


def test_finished_message_requires_winner(session):
    with pytest.raises(ValueError, match="no winner yet"):
        ws_service.build_penalty_shootout_finished_message(
            session.shootout,
        )

    for _ in range(6):
        session.shootout.resolve_penalty(
            PenaltySide.LEFT,
            PenaltySide.RIGHT,
        )

    message = ws_service.build_penalty_shootout_finished_message(
        session.shootout,
    )

    assert message.model_dump(mode="json") == {
        "event": "penalty_shootout_finished",
        "winner_club_id": session.shootout.winner_club_id,
        "score_club_a": 3,
        "score_club_b": 3,
    }


@pytest.mark.asyncio
async def test_broadcast_serializes_penalty_sides(result_message):
    manager = ws_service.MatchConnectionManager()
    first = AsyncMock()
    second = AsyncMock()
    manager.active_connections[100] = [first, second]

    await manager.broadcast(100, result_message)

    expected = {
        "event": "penalty_result",
        "turn": 1,
        "club_id": 10,
        "kicker": 11,
        "kick_side": "LEFT",
        "save_side": "RIGHT",
        "is_goal": True,
        "score_club_a": 1,
        "score_club_b": 0,
    }

    first.send_json.assert_awaited_once_with(expected)
    second.send_json.assert_awaited_once_with(expected)


@pytest.mark.asyncio
@pytest.mark.parametrize("message_kind", ["penalty", "match_state"])
async def test_send_timeout_removes_socket_and_continues(
    monkeypatch,
    result_message,
    message_kind,
):
    monkeypatch.setattr(ws_service, "SEND_TIMEOUT_SECONDS", 0.01)

    manager = ws_service.MatchConnectionManager()
    slow = AsyncMock()
    healthy = AsyncMock()
    slow.send_json.side_effect = block_socket

    manager.active_connections[100] = [slow, healthy]
    manager.connection_clubs[slow] = 10
    manager.connection_clubs[healthy] = 20

    if message_kind == "match_state":
        message = MatchStateMessage(
            event="estado_partido",
            actual_tic=4,
            total_tic=4,
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
    else:
        message = result_message

    await asyncio.wait_for(
        manager.broadcast(100, message),
        timeout=1.0,
    )

    slow.send_json.assert_awaited_once()
    healthy.send_json.assert_awaited_once_with(
        message.model_dump(mode="json"),
    )

    assert manager.active_connections[100] == [healthy]
    assert slow not in manager.connection_clubs
    assert manager.connection_clubs[healthy] == 20


@pytest.mark.asyncio
async def test_close_timeout_still_closes_remaining_sockets(monkeypatch):
    monkeypatch.setattr(ws_service, "SEND_TIMEOUT_SECONDS", 0.01)

    manager = ws_service.MatchConnectionManager()
    slow = AsyncMock()
    healthy = AsyncMock()
    slow.close.side_effect = block_socket

    manager.active_connections[100] = [slow, healthy]
    manager.connection_clubs[slow] = 10
    manager.connection_clubs[healthy] = 20

    await asyncio.wait_for(
        manager.close_match_connection(100),
        timeout=1.0,
    )

    slow.close.assert_awaited_once()
    healthy.close.assert_awaited_once()

    assert 100 not in manager.active_connections
    assert slow not in manager.connection_clubs
    assert healthy not in manager.connection_clubs
