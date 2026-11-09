import asyncio
import copy

import pytest

import asyncio
from functools import partial
from itertools import count

from types import SimpleNamespace
from unittest.mock import MagicMock, AsyncMock, call

from app.game.match_runner import (
    MatchRunner,
    BehaviorCoordinatorProtocol,
    GameEngineProtocol
)
import app.game.match_runner as match_runner_module
from app.game.models.ball import Ball
from app.game.models.match import Match, MatchState
from app.game.models.match_participation import MatchParticipation
import app.game.penalty_session as penalty_session_module


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
        duration_ticks=40,
    )

# we create a magicmock and assign it the attributes/methods of the class in spec
@pytest.fixture
def behavior_coordinator():
    coordinator = MagicMock(
        spec=BehaviorCoordinatorProtocol
    )

    # execute_all is asynchronous.
    coordinator.get_actions.return_value = ["wait"] * 6

    return coordinator


@pytest.fixture
def game_engine():
    return MagicMock(
        spec=GameEngineProtocol
    )


@pytest.fixture(autouse=True)
def disable_tick_delay(monkeypatch):
    monkeypatch.setattr(
        "app.game.match_runner.TIC_DURATION",
        0,
    )


@pytest.mark.asyncio
async def test_execute_tick_advances_one_tick(match,behavior_coordinator,game_engine):
    initial_tick = match.current_tick

    # prepare a MatchRunner
    runner = MatchRunner(
        behavior_coordinator,
        game_engine,
        hydration_duration=0,
        halftime_duration=0,
        execution_window=0,
    )
    # and execute one tick
    await runner.execute_tick(match)

    assert match.current_tick == initial_tick + 1

@pytest.mark.asyncio
async def test_run_match_executes_behaviors_once_per_tick(match,behavior_coordinator,game_engine):
    match.duration_ticks = 4

    runner = MatchRunner(
        behavior_coordinator,
        game_engine,
        hydration_duration=0,
        halftime_duration=0,
        execution_window=0,
    )

    # execute the entire match
    await runner.run_match(match)
    # use magicmock functionrs to count
    assert behavior_coordinator.get_actions.call_count == 4

@pytest.mark.asyncio
async def test_behavior_executor_and_engine_use_same_snapshot(
    match,
    behavior_coordinator,
    game_engine,
):
    runner = MatchRunner(
        behavior_coordinator,
        game_engine,
        hydration_duration=0,
        halftime_duration=0,
        execution_window=0,
    )

    await runner.execute_tick(match)

    # use magic mock functionrs
    # we get the first argument with which it went inside execute tick
    snapshot_received_by_behavior_executor = (
        behavior_coordinator
        .get_actions
        .call_args
        .args[0]
    )

    # we get the second argument with which it went inside execute tick
    snapshot_received_by_engine = (
        game_engine
        .step
        .call_args
        .args[1]
    )

    assert (snapshot_received_by_behavior_executor is snapshot_received_by_engine)

@pytest.mark.asyncio
async def test_actions_are_sent_to_engine(
    match,
    behavior_coordinator,
    game_engine,
):
    runner = MatchRunner(
        behavior_coordinator,
        game_engine,
        hydration_duration=0,
        halftime_duration=0,
        execution_window=0,
    )

    await runner.execute_tick(match)

    actions_received_by_engine = (
        game_engine
        .step
        .call_args
        .args[2]
    )

    assert actions_received_by_engine == ["wait"] * 6

@pytest.mark.asyncio
async def test_generated_state_is_used_in_next_tick(
    match,
    behavior_coordinator,
    game_engine,
):
    # change the duration only for this test
    match.duration_ticks = 4

    initial_ball_position = match.ball.position

    # the real engine is not implemented yet,
    # so we simulate that it changes the state of the ball.
    def engine_step(match, snapshot, actions):
        match.ball.position = (
            snapshot.ball.position[0] + 1,
            snapshot.ball.position[1],
        )

    game_engine.step.side_effect = engine_step

    runner = MatchRunner(
        behavior_coordinator,
        game_engine,
        hydration_duration=0,
        halftime_duration=0,
        execution_window=0,
    )

    await runner.run_match(match)

    first_snapshot = (
        behavior_coordinator
        .get_actions
        .call_args_list[0]
        .args[0]
    )

    second_snapshot = (
        behavior_coordinator
        .get_actions
        .call_args_list[1]
        .args[0]
    )

    # state used for the first tick.
    assert first_snapshot.current_tick == 0
    assert first_snapshot.ball.position == initial_ball_position

    # state generated by the first tick is used by the second tick.
    assert second_snapshot.current_tick == 1

    assert second_snapshot.ball.position == (
        initial_ball_position[0] + 1,
        initial_ball_position[1],
    )

@pytest.mark.asyncio
async def test_run_match_stops_at_duration_ticks(
    match,
    behavior_coordinator,
    game_engine,
):

    runner = MatchRunner(
        behavior_coordinator,
        game_engine,
        hydration_duration=0,
        halftime_duration=0,
        execution_window=0,
    )

    await runner.run_match(match)
    # wait for the match to end and then verify
    assert match.current_tick == 40

    assert behavior_coordinator.get_actions.call_count == 40
    assert game_engine.step.call_count == 40

    assert match.state == MatchState.FINISHED


class FakeClock:
    """
    Simulate time progression with a fixed scheduling delay.
    """

    def __init__(
        self,
        tick_duration: float = 0.020,
        scheduling_delay: float = 0.003,
    ):
        self.current_time = 0.0
        self.tick_duration = tick_duration
        self.scheduling_delay = scheduling_delay
        self.tick_starts = []

    def monotonic(self) -> float:
        return self.current_time

    async def sleep(self, seconds: float) -> None:
        self.current_time += seconds + self.scheduling_delay

    async def execute_tick(self, match: Match) -> None:
        self.tick_starts.append(self.current_time)
        self.current_time += self.tick_duration
        match.current_tick += 1


@pytest.mark.asyncio
async def test_run_match_does_not_accumulate_tick_drift(
    match,
    behavior_coordinator,
    game_engine,
    monkeypatch,
):
    match.duration_ticks = 8

    clock = FakeClock()

    runner = MatchRunner(
        behavior_coordinator,
        game_engine,
        hydration_duration=0,
        halftime_duration=0,
        execution_window=0,
    )

    async def fake_period_break(match):
        pass

    monkeypatch.setattr(
        runner,
        "handle_period_break",
        fake_period_break,
    )

    monkeypatch.setattr(
        match_runner_module,
        "TIC_DURATION",
        0.1,
    )

    monkeypatch.setattr(
        match_runner_module,
        "time",
        SimpleNamespace(monotonic=clock.monotonic),
    )

    monkeypatch.setattr(
        match_runner_module,
        "asyncio",
        SimpleNamespace(sleep=clock.sleep, to_thread=asyncio.to_thread),
    )

    monkeypatch.setattr(
        runner,
        "execute_tick",
        clock.execute_tick,
    )

    monkeypatch.setattr(
        match_runner_module.match_connection_manager,
        "broadcast",
        AsyncMock(),
    )

    monkeypatch.setattr(
        match_runner_module.match_connection_manager,
        "close_match_connection",
        AsyncMock(),
    )

    await runner.run_match(match)

    assert clock.tick_starts == pytest.approx([
        0.000,
        0.103,
        0.203,
        0.306,
        0.406,
        0.509,
        0.609,
        0.712,
    ])

    assert clock.current_time == pytest.approx(0.812)
    assert match.current_tick == 8
    assert match.state == MatchState.FINISHED

@pytest.mark.asyncio
@pytest.mark.parametrize("break_duration", [10.0, 20.0])
async def test_match_does_not_catch_up_ticks_after_break(
    match,
    behavior_coordinator,
    game_engine,
    monkeypatch,
    break_duration,
):
    match.duration_ticks = 8

    clock = FakeClock(
        tick_duration=0.020,
        scheduling_delay=0.0,
    )

    runner = MatchRunner(
        behavior_coordinator,
        game_engine,
        hydration_duration=0,
        halftime_duration=0,
        execution_window=0,
    )

    monkeypatch.setattr(
        match_runner_module,
        "TIC_DURATION",
        0.1,
    )

    monkeypatch.setattr(
        match_runner_module,
        "time",
        SimpleNamespace(monotonic=clock.monotonic),
    )

    monkeypatch.setattr(
        match_runner_module,
        "asyncio",
        SimpleNamespace(sleep=clock.sleep, to_thread=asyncio.to_thread),
    )

    monkeypatch.setattr(
        runner,
        "execute_tick",
        clock.execute_tick,
    )

    async def fake_period_break(match):
        # emule a real pause without wait
        clock.current_time += break_duration

    monkeypatch.setattr(
        runner,
        "handle_period_break",
        fake_period_break,
    )

    monkeypatch.setattr(
        match_runner_module.match_connection_manager,
        "broadcast",
        AsyncMock(),
    )

    monkeypatch.setattr(
        match_runner_module.match_connection_manager,
        "close_match_connection",
        AsyncMock(),
    )

    await runner.run_match(match)

    for first_tick_after_break in (2, 4, 6):
        previous_tick = clock.tick_starts[first_tick_after_break - 1]
        resumed_tick = clock.tick_starts[first_tick_after_break]

        assert resumed_tick - previous_tick == pytest.approx(
            break_duration + 0.1
        )

        assert (
            clock.tick_starts[first_tick_after_break + 1]
            - resumed_tick
        ) == pytest.approx(0.1)

    assert match.current_tick == 8
    assert match.state == MatchState.FINISHED


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("goals_a", "goals_b", "expected_winner"),
    [
        pytest.param(2, 1, 1, id="home-wins"),
        pytest.param(1, 2, 2, id="away-wins"),
        pytest.param(1, 1, None, id="draw"),
    ],
)
async def test_run_match_sets_regulation_winner(
    match,
    behavior_coordinator,
    game_engine,
    goals_a,
    goals_b,
    expected_winner,
):
    match.duration_ticks = 4
    match.participation_a.goals = goals_a
    match.participation_b.goals = goals_b

    assert match.winner_club_id is None

    runner = MatchRunner(
        behavior_coordinator,
        game_engine,
        hydration_duration=0,
        halftime_duration=0,
        execution_window=0,
    )

    result = await runner.run_match(match)

    assert result.state == MatchState.FINISHED
    assert result.winner_club_id == expected_winner
    assert result.snapshot().winner_club_id == expected_winner

    assert result.participation_a.goals == goals_a
    assert result.participation_b.goals == goals_b


# Penalty tests

class PenaltyPauseProbe:
    def __init__(self, match):
        self.match = match
        self.states = []

    async def sleep(self, duration):
        session = self.match.penalty_session
        self.states.append((
            session.shootout.turn,
            session.accepting_choices,
            self.match.winner_club_id,
            session.shootout.winner_club_id,
        ))


@pytest.fixture
def penalty_runner(behavior_coordinator, game_engine):
    return MatchRunner(
        behavior_coordinator,
        game_engine,
        hydration_duration=0,
        halftime_duration=0,
        execution_window=0,
        penalty_intro_duration=0,
        penalty_result_duration=0,
    )


@pytest.fixture
def penalty_connections(monkeypatch):
    connections = SimpleNamespace(
        broadcast=AsyncMock(),
        close_match_connection=AsyncMock(),
    )
    monkeypatch.setattr(
        match_runner_module,
        "match_connection_manager",
        connections,
    )
    return connections


@pytest.fixture
def expired_penalty_clock(monkeypatch):
    # Advance beyond the five-second deadline on each clock read.
    monkeypatch.setattr(
        penalty_session_module,
        "monotonic",
        partial(next, count(start=100, step=10)),
    )


class ControlledPenaltyRun:
    def __init__(self):
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def __call__(self, *, match, turn_timeout):
        self.started.set()
        await self.release.wait()
        match.winner_club_id = match.participation_b.club_id


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "enabled, goals_a, goals_b, expected_winner",
    [
        pytest.param(False, 1, 1, None, id="draw-allowed"),
        pytest.param(False, 2, 1, 1, id="home-regulation-win"),
        pytest.param(False, 1, 2, 2, id="away-regulation-win"),
        pytest.param(True, 2, 1, 1, id="home-win-no-shootout"),
        pytest.param(True, 1, 2, 2, id="away-win-no-shootout"),
    ],
)
async def test_run_match_skips_unnecessary_penalties(
    match,
    penalty_runner,
    penalty_connections,
    monkeypatch,
    enabled,
    goals_a,
    goals_b,
    expected_winner,
):
    match.duration_ticks = 4
    match.penalties_enabled = enabled
    match.participation_a.goals = goals_a
    match.participation_b.goals = goals_b

    penalties = AsyncMock()
    monkeypatch.setattr(penalty_runner, "run_penalties", penalties)

    result = await penalty_runner.run_match(match)

    penalties.assert_not_awaited()
    assert result.winner_club_id == expected_winner
    assert result.penalty_session is None
    assert result.state == MatchState.FINISHED
    assert result.participation_a.goals == goals_a
    assert result.participation_b.goals == goals_b

    penalty_connections.close_match_connection.assert_awaited_once_with(
        match.match_id,
    )


@pytest.mark.asyncio
async def test_tied_match_runs_all_penalties_with_current_starters(
    match,
    penalty_runner,
    penalty_connections,
    expired_penalty_clock,
):
    match.duration_ticks = 4
    match.penalties_enabled = True
    match.participation_a.goals = 1
    match.participation_b.goals = 1

    # Replace one starter on each team before the shootout.
    for participation in (
        match.participation_a,
        match.participation_b,
    ):
        participation.players[0].is_on_field = False
        participation.players[3].is_on_field = True

    result = await penalty_runner.run_match(match)

    session = result.penalty_session
    assert session is not None

    shootout = session.shootout
    assert shootout.turn == 6
    assert shootout.seed == match.match_id
    assert shootout.kickers_a == (2, 3, 4)
    assert shootout.kickers_b == (8, 9, 10)
    assert session.accepting_choices is False

    assert result.winner_club_id in (
        match.participation_a.club_id,
        match.participation_b.club_id,
    )
    assert result.winner_club_id == shootout.winner_club_id
    assert result.snapshot().winner_club_id == shootout.winner_club_id

    assert result.participation_a.goals == 1
    assert result.participation_b.goals == 1
    assert result.current_tick == result.duration_ticks
    assert result.state == MatchState.FINISHED

    penalty_connections.close_match_connection.assert_awaited_once_with(
        match.match_id,
    )


@pytest.mark.asyncio
async def test_match_waits_for_penalties_before_finishing(
    match,
    penalty_runner,
    penalty_connections,
    monkeypatch,
):
    match.duration_ticks = 4
    match.penalties_enabled = True

    penalties = ControlledPenaltyRun()
    monkeypatch.setattr(
        penalty_runner,
        "run_penalties",
        penalties,
    )

    task = asyncio.create_task(penalty_runner.run_match(match))

    try:
        await asyncio.wait_for(penalties.started.wait(), timeout=1.0)

        assert not task.done()
        assert match.state == MatchState.IN_PROGRESS
        assert match.substitution_requests_open is False
        assert match.winner_club_id is None
        penalty_connections.close_match_connection.assert_not_awaited()

        penalties.release.set()
        result = await asyncio.wait_for(task, timeout=1.0)

        assert result.state == MatchState.FINISHED
        assert result.winner_club_id == match.participation_b.club_id
        penalty_connections.close_match_connection.assert_awaited_once_with(
            match.match_id,
        )
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_penalty_failure_does_not_finish_match(
    match,
    penalty_runner,
    penalty_connections,
    monkeypatch,
):
    match.duration_ticks = 4
    match.penalties_enabled = True

    penalties = AsyncMock(
        side_effect=RuntimeError("Penalty execution failed"),
    )
    monkeypatch.setattr(
        penalty_runner,
        "run_penalties",
        penalties,
    )

    with pytest.raises(RuntimeError, match="Penalty execution failed"):
        await penalty_runner.run_match(match)

    penalties.assert_awaited_once()
    assert match.state == MatchState.IN_PROGRESS
    assert match.winner_club_id is None
    assert match.substitution_requests_open is False
    penalty_connections.close_match_connection.assert_not_awaited()


@pytest.mark.asyncio
async def test_penalty_events_are_emitted_before_socket_closes(
    match,
    penalty_runner,
    penalty_connections,
    expired_penalty_clock,
):
    match.duration_ticks = 4
    match.penalties_enabled = True

    timeline = MagicMock()
    timeline.attach_mock(penalty_connections.broadcast, "broadcast")
    timeline.attach_mock(
        penalty_connections.close_match_connection,
        "close",
    )

    await penalty_runner.run_match(match)

    events = [
        awaited.args[1]
        for awaited in penalty_connections.broadcast.await_args_list
        if awaited.args[1].event.startswith("penalty_")
    ]

    assert [message.event for message in events] == (
        ["penalty_shootout_started"]
        + ["penalty_turn_started", "penalty_result"] * 6
        + ["penalty_shootout_finished"]
    )

    started = [
        message
        for message in events
        if message.event == "penalty_turn_started"
    ]

    results = [
        message
        for message in events
        if message.event == "penalty_result"
    ]

    assert [message.turn for message in started] == list(range(1, 7))
    assert [message.turn for message in results] == list(range(1, 7))
    assert [message.club_id for message in started] == [1, 2] * 3
    assert [message.kicker for message in started] == [1, 7, 2, 8, 3, 9]

    for start, result in zip(started, results):
        assert result.club_id == start.club_id
        assert result.kicker == start.kicker

    finished = events[-1]
    shootout = match.penalty_session.shootout

    assert finished.winner_club_id == match.winner_club_id
    assert finished.score_club_a == shootout.score_a
    assert finished.score_club_b == shootout.score_b

    assert timeline.mock_calls[-1] == call.close(match.match_id)


class CancelPenaltyDelivery:
    def __init__(self, event):
        self.event = event

    async def broadcast(self, match_id, message):
        if message.event == self.event:
            raise asyncio.CancelledError()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "event, expected_resolved_turns",
    [
        ("penalty_turn_started", 0),
        ("penalty_result", 1),
    ],
)
async def test_cancellation_during_penalty_delivery_closes_turn(
    match,
    penalty_runner,
    penalty_connections,
    expired_penalty_clock,
    event,
    expected_resolved_turns,
):
    match.duration_ticks = 4
    match.penalties_enabled = True

    cancellation = CancelPenaltyDelivery(event)
    penalty_connections.broadcast.side_effect = cancellation.broadcast

    with pytest.raises(asyncio.CancelledError):
        await penalty_runner.run_match(match)

    session = match.penalty_session

    assert session is not None
    assert session.accepting_choices is False
    assert session.shootout.turn == expected_resolved_turns
    assert match.state == MatchState.IN_PROGRESS
    assert match.winner_club_id is None
    penalty_connections.close_match_connection.assert_not_awaited()


@pytest.mark.asyncio
async def test_penalty_pauses_happen_before_next_turn_and_finalization(
    match,
    penalty_runner,
    penalty_connections,
    expired_penalty_clock,
    monkeypatch,
):
    penalty_runner.penalty_intro_duration = 1.5
    penalty_runner.penalty_result_duration = 2.5

    probe = PenaltyPauseProbe(match)
    sleep = AsyncMock(side_effect=probe.sleep)

    # Replace only the runner's asyncio reference.
    monkeypatch.setattr(
        match_runner_module,
        "asyncio",
        SimpleNamespace(sleep=sleep),
    )

    timeline = MagicMock()
    timeline.attach_mock(penalty_connections.broadcast, "broadcast")
    timeline.attach_mock(sleep, "sleep")

    await penalty_runner.run_penalties(
        match=match,
        turn_timeout=5.0,
    )

    # Introduction, then six turn/result/pause sequences, then finalization.
    assert [operation[0] for operation in timeline.mock_calls] == (
        ["broadcast", "sleep"]
        + ["broadcast", "broadcast", "sleep"] * 6
        + ["broadcast"]
    )

    assert sleep.await_args_list == (
        [call(1.5)] + [call(2.5)] * 6
    )

    messages = [
        awaited.args[1]
        for awaited in penalty_connections.broadcast.await_args_list
    ]

    assert messages[0].event == "penalty_shootout_started"
    assert messages[0].duration == 1.5

    results = [
        message
        for message in messages
        if message.event == "penalty_result"
    ]
    assert len(results) == 6
    assert all(message.duration == 2.5 for message in results)

    # Choices remain closed and the match winner remains unconfirmed
    # throughout the introduction and all six result pauses.
    assert [
        state[:3]
        for state in probe.states
    ] == [
        (resolved_turns, False, None)
        for resolved_turns in range(7)
    ]

    # The shootout already knows its winner during the last pause.
    assert probe.states[-1][3] in (
        match.participation_a.club_id,
        match.participation_b.club_id,
    )

    assert messages[-1].event == "penalty_shootout_finished"
    assert messages[-1].winner_club_id == match.winner_club_id
    assert match.winner_club_id == match.penalty_session.shootout.winner_club_id
