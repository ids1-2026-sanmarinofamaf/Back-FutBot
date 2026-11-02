
import asyncio
import copy
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.game import match_runner as match_runner_module
from app.game.constants import FIELD_CENTER, FIELD_WIDTH
from app.game.engine import GameEngine
from app.game.match_runner import (
    MatchRunner,
    BehaviorCoordinatorProtocol,
    GameEngineProtocol,
)
from app.game.models.ball import Ball
from app.game.models.match import Match, MatchState
from app.game.models.match_participation import MatchParticipation
from app.game.types import Period, Side


@pytest.fixture
def match(six_players):
    players_a = copy.deepcopy(six_players)
    players_b = copy.deepcopy(six_players)

    for player in players_b:
        player.player_id += 6

        if player.starting_position is not None:
            x, y = player.starting_position
            player.starting_position = (FIELD_WIDTH - x, y)
            player.position = player.starting_position

    return Match(
        match_id=1,
        participation_a=MatchParticipation(
            club_id=1,
            roster_id=1,
            players=players_a,
        ),
        participation_b=MatchParticipation(
            club_id=2,
            roster_id=2,
            players=players_b,
        ),
        ball=Ball(
            position=FIELD_CENTER,
            velocity=(0.0, 0.0),
        ),
        duration_ticks=8,
    )


@pytest.fixture
def coordinator():
    mock = MagicMock(spec=BehaviorCoordinatorProtocol)
    mock.get_actions.return_value = ["wait"] * 6
    return mock


@pytest.fixture
def engine():
    return MagicMock(spec=GameEngineProtocol)


@pytest.fixture
def websocket_manager(monkeypatch):
    manager = MagicMock()
    manager.broadcast = AsyncMock()
    manager.close_match_connection = AsyncMock()

    monkeypatch.setattr(
        match_runner_module,
        "match_connection_manager",
        manager,
    )

    return manager


def create_runner(coordinator, engine):
    # use zero-duration breaks to keep tests fast
    return MatchRunner(
        coordinator,
        engine,
        hydration_duration=0,
        halftime_duration=0,
        execution_window=0,
    )


@pytest.mark.asyncio
async def test_breaks_occur_at_correct_ticks(match, coordinator, engine, websocket_manager):
    runner = create_runner(coordinator, engine)

    # the match has 8 ticks, so each period has 2 ticks
    match.state = MatchState.IN_PROGRESS

    await runner.execute_tick(match)
    await runner.execute_tick(match)

    assert match.current_tick == 2
    assert runner.is_period_end(match)

    await runner.handle_period_break(match)

    assert match.current_period == Period.SECOND_QUARTER

    await runner.execute_tick(match)
    await runner.execute_tick(match)

    assert match.current_tick == 4
    assert runner.is_period_end(match)

    await runner.handle_period_break(match)

    assert match.current_period == Period.THIRD_QUARTER

    await runner.execute_tick(match)
    await runner.execute_tick(match)

    assert match.current_tick == 6
    assert runner.is_period_end(match)

    await runner.handle_period_break(match)

    assert match.current_period == Period.FOURTH_QUARTER

    await runner.execute_tick(match)
    await runner.execute_tick(match)

    assert match.current_tick == 8
    assert not runner.is_period_end(match)

@pytest.mark.asyncio
async def test_ticks_and_behaviors_stop_during_break(match, coordinator, engine, websocket_manager):
    runner = MatchRunner(
        coordinator,
        engine,
        hydration_duration=0.3,
        halftime_duration=0.3,
        execution_window=0.1,
    )

    match.state = MatchState.IN_PROGRESS

    # execute the first period
    await runner.execute_tick(match)
    await runner.execute_tick(match)

    # check ticks and behavior executions before the break
    assert match.current_tick == 2
    assert coordinator.get_actions.call_count == 2
    assert engine.step.call_count == 2

    # execute the break 
    await runner.handle_period_break(match)

    # check that no ticks or behaviors were executed during the break
    assert match.current_tick == 2
    assert coordinator.get_actions.call_count == 2
    assert engine.step.call_count == 2

    assert match.current_period == Period.SECOND_QUARTER

    # execute the first tick of the next period
    await runner.execute_tick(match)

    assert match.current_tick == 3
    assert coordinator.get_actions.call_count == 3
    assert engine.step.call_count == 3

@pytest.mark.asyncio
async def test_all_periods_have_equal_duration(match, coordinator, engine, websocket_manager):
    runner = create_runner(coordinator, engine)
    await runner.run_match(match)

    # get the period of each executed tick
    periods = [
        call.args[0].current_period
        for call in coordinator.get_actions.call_args_list
    ]

    assert periods.count(Period.FIRST_QUARTER) == 2
    assert periods.count(Period.SECOND_QUARTER) == 2
    assert periods.count(Period.THIRD_QUARTER) == 2
    assert periods.count(Period.FOURTH_QUARTER) == 2

    assert match.current_tick == 8


@pytest.mark.asyncio
async def test_positions_reset_after_hydration(match, coordinator, websocket_manager):
    engine = GameEngine()
    runner = create_runner(coordinator, engine)

    match.state = MatchState.IN_PROGRESS
    match.current_tick = 2

    player = match.participation_a.players[0]

    # move a player and the ball away from their starting positions
    player.position = (15.0, 8.0)
    player.velocity = (1.0, 0.0)

    match.ball.position = (10.0, 4.0)
    match.ball.velocity = (2.0, 1.0)

    await runner.handle_period_break(match)
    # verify starting position after the break
    for participation in (
        match.participation_a,
        match.participation_b,
    ):
        for player in participation.players:
            if player.is_on_field:
                assert player.position == player.starting_position
                assert player.velocity == (0.0, 0.0)

    assert match.ball.position == FIELD_CENTER
    assert match.ball.velocity == (0.0, 0.0)

    assert match.current_period == Period.SECOND_QUARTER


@pytest.mark.asyncio
async def test_teams_switch_sides_at_halftime(match, coordinator, websocket_manager):
    engine = GameEngine()
    runner = create_runner(coordinator, engine)

    match.state = MatchState.IN_PROGRESS
    match.current_tick = 4
    match.current_period = Period.SECOND_QUARTER

    player_a = match.participation_a.players[0]
    player_b = match.participation_b.players[0]

    original_a = player_a.starting_position
    original_b = player_b.starting_position

    await runner.handle_period_break(match)

    # teams exchange defending sides
    assert match.side_a == Side.RIGHT
    assert match.side_b == Side.LEFT

    # starting positions are mirrored horizontally
    assert player_a.position == (
        FIELD_WIDTH - original_a[0],
        original_a[1],
    )

    assert player_b.position == (
        FIELD_WIDTH - original_b[0],
        original_b[1],
    )

    # the ball returns to the center
    assert match.ball.position == FIELD_CENTER

    assert match.current_period == Period.THIRD_QUARTER


@pytest.mark.asyncio
async def test_pause_websocket_events(match, coordinator, engine, websocket_manager):
    runner = create_runner(coordinator, engine)

    await runner.run_match(match)

    # get all messages sent by the match runner
    messages = [
        call.args[1]
        for call in websocket_manager.broadcast.await_args_list
    ]

    started = [
        message
        for message in messages
        if message.event == "pause_started"
    ]

    finished = [
        message
        for message in messages
        if message.event == "pause_finished"
    ]

    assert len(started) == 3
    assert len(finished) == 3

    assert [message.pause_type for message in started] == [
        "hydration",
        "halftime",
        "hydration",
    ]

    assert [message.pause_type for message in finished] == [
        "hydration",
        "halftime",
        "hydration",
    ]

    assert all(message.duration == 0 for message in started)


@pytest.mark.asyncio
async def test_match_finishes_without_fourth_break(match, coordinator, engine, websocket_manager):
    runner = create_runner(coordinator, engine)

    await runner.run_match(match)

    assert match.current_tick == match.duration_ticks
    assert match.current_period == Period.FOURTH_QUARTER
    assert match.state == MatchState.FINISHED

    # every tick executes exactly once
    assert coordinator.get_actions.call_count == 8
    assert engine.step.call_count == 8

    # the WebSocket connection is closed when the match finishes
    websocket_manager.close_match_connection.assert_awaited_once_with(match.match_id)
