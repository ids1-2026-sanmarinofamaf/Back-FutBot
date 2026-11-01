"""
Tests for the coach (DT) execution during a match: triggers, context,
primitives, executor, worker pool, coordinator and match runner.
"""

import copy
from textwrap import dedent
from unittest.mock import MagicMock

import pytest

from app.game.behavior_coordinator import BehaviorCoordinator
from app.game.behavior_executor import execute_coach_behavior
from app.game.behavior_worker_pool import BehaviorWorkerPool, CoachJob
from app.game.context import set_current_context, clear_current_context
from app.game.context_builder import build_coach_context
from app.game.engine import GameEngine
from app.game.match_runner import MatchRunner
from app.game.models.ball import Ball
from app.game.models.behavior_definition import BehaviorDefinition
from app.game.models.match import Match, MatchState
from app.game.models.match_participation import MatchParticipation
from app.game.models.runtime_behavior import RuntimeCoachBehavior
from app.game.primitives import assign, trigger, current_behavior, available_behaviors
from app.game.types import CoachTrigger, Period, Side
from app.services.match_websocket_service import build_coach_changes_message


@pytest.fixture
def match(six_players):
    players_a = copy.deepcopy(six_players)
    players_b = copy.deepcopy(six_players)

    for player in players_b:
        player.player_id += 6

    participation_a = MatchParticipation(
        club_id=1,
        roster_id=1,
        players=players_a,
        coach_behavior_id=50,
        available_behaviors={"Attacker": 1, "Defender": 2},
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
        state=MatchState.IN_PROGRESS,
    )


@pytest.fixture
def coach_context(match):
    return build_coach_context(
        match,
        match.participation_a,
        CoachTrigger.GOAL_FOR,
    )


# triggers

def test_goal_registers_goal_for_and_goal_against(match):
    GameEngine()._handle_goal(match, Side.LEFT)

    assert match.pending_coach_triggers == [
        (2, CoachTrigger.GOAL_FOR),
        (1, CoachTrigger.GOAL_AGAINST),
    ]


def test_period_start_registers_trigger_for_both_clubs(match):
    match.close_and_execute_substitutions()

    match.start_next_period(Period.SECOND_QUARTER)

    assert match.pending_coach_triggers == [
        (1, CoachTrigger.PERIOD_START),
        (2, CoachTrigger.PERIOD_START),
    ]


# context

def test_coach_context_contains_club_perspective(match):
    match.participation_a.goals = 2
    match.participation_b.goals = 1

    context = build_coach_context(
        match,
        match.participation_a,
        CoachTrigger.GOAL_FOR,
    )

    assert [player_id for player_id, _ in context.teammates] == [1, 2, 3]
    assert [player_id for player_id, _ in context.opponents] == [7, 8, 9]
    assert context.my_team_score == 2
    assert context.opponent_score == 1
    assert context.side == Side.LEFT
    assert context.trigger == CoachTrigger.GOAL_FOR
    assert context.available_behaviors == ["Attacker", "Defender"]
    assert context.current_behaviors == {1: "Attacker", 2: "Attacker", 3: "Attacker"}


def test_coach_context_for_right_side(match):
    context = build_coach_context(
        match,
        match.participation_b,
        CoachTrigger.PERIOD_START,
    )

    assert context.side == Side.RIGHT
    assert [player_id for player_id, _ in context.teammates] == [7, 8, 9]


# primitives

def test_coach_primitives_read_coach_context(coach_context):
    set_current_context(coach_context)

    try:
        assert trigger() == CoachTrigger.GOAL_FOR
        assert available_behaviors() == ["Attacker", "Defender"]
        assert current_behavior(1) == "Attacker"
        assert current_behavior(99) is None
        assert assign(1, "Defender") == (1, "Defender")
    finally:
        clear_current_context()


# executor

def test_execute_coach_behavior_returns_assignments(coach_context):
    behavior = RuntimeCoachBehavior(
        id=1,
        coach=lambda: [(1, "Defender"), (2, "Attacker")],
    )

    assert execute_coach_behavior(coach_context, behavior) == [
        (1, "Defender"),
        (2, "Attacker"),
    ]


def test_execute_coach_behavior_discards_malformed_assignments(coach_context):
    behavior = RuntimeCoachBehavior(
        id=1,
        coach=lambda: [(1, "Defender"), "bad", (True, "Attacker"), (2, 3)],
    )

    assert execute_coach_behavior(coach_context, behavior) == [(1, "Defender")]


def test_execute_coach_behavior_returns_empty_list_on_error(coach_context):
    def failing_coach():
        raise RuntimeError("boom")

    behavior = RuntimeCoachBehavior(id=1, coach=failing_coach)

    assert execute_coach_behavior(coach_context, behavior) == []


def test_execute_coach_behavior_returns_empty_list_if_not_a_list(coach_context):
    behavior = RuntimeCoachBehavior(id=1, coach=lambda: (1, "Defender"))

    assert execute_coach_behavior(coach_context, behavior) == []


# worker pool

COACH_CODE = dedent(
    """
    def coach():
        if trigger() == CoachTrigger.GOAL_FOR:
            return [assign(player_id, "Defender") for player_id, _ in teammates()]
        return []
    """
)


def test_pool_executes_registered_coach(coach_context):
    pool = BehaviorWorkerPool(size=1)

    try:
        pool.register_coach_behaviors([
            BehaviorDefinition(id=50, code=COACH_CODE),
        ])

        results = pool.execute_coach([
            CoachJob(club_id=1, coach_behavior_id=50, context=coach_context),
        ])

        assert results == [[(1, "Defender"), (2, "Defender"), (3, "Defender")]]
    finally:
        pool.shutdown()


def test_pool_returns_empty_list_for_unknown_coach(coach_context):
    pool = BehaviorWorkerPool(size=1)

    try:
        results = pool.execute_coach([
            CoachJob(club_id=1, coach_behavior_id=999, context=coach_context),
        ])

        assert results == [[]]
    finally:
        pool.shutdown()


def test_pool_returns_empty_list_on_coach_timeout(coach_context):
    pool = BehaviorWorkerPool(size=1, timeout_ms=100)

    try:
        pool.register_coach_behaviors([
            BehaviorDefinition(
                id=50,
                code="def coach():\n    while True:\n        pass\n",
            ),
        ])

        results = pool.execute_coach([
            CoachJob(club_id=1, coach_behavior_id=50, context=coach_context),
        ])

        assert results == [[]]
        assert pool._processes[0].is_alive()
    finally:
        pool.shutdown()


def test_pool_coach_registry_does_not_overwrite_player_behaviors(coach_context):
    pool = BehaviorWorkerPool(size=1)

    try:
        pool.register_behaviors([
            BehaviorDefinition(id=50, code="def play():\n    return wait()\n"),
        ])
        pool.register_coach_behaviors([
            BehaviorDefinition(id=50, code=COACH_CODE),
        ])

        assert pool._registered_behaviors[50].code != COACH_CODE
        assert pool._registered_coach_behaviors[50].code == COACH_CODE
    finally:
        pool.shutdown()


# coordinator

def test_coordinator_skips_clubs_without_coach(match):
    worker_pool = MagicMock()
    worker_pool.execute_coach.return_value = [[(1, "Defender")]]

    coordinator = BehaviorCoordinator(worker_pool)

    assignments = coordinator.get_coach_assignments(
        match,
        [(1, CoachTrigger.GOAL_FOR), (2, CoachTrigger.GOAL_AGAINST)],
    )

    jobs = worker_pool.execute_coach.call_args.args[0]

    assert [job.club_id for job in jobs] == [1]
    assert assignments == {1: [(1, "Defender")]}


def test_coordinator_does_not_call_pool_without_jobs(match):
    worker_pool = MagicMock()

    coordinator = BehaviorCoordinator(worker_pool)

    assignments = coordinator.get_coach_assignments(
        match,
        [(2, CoachTrigger.GOAL_FOR)],
    )

    assert assignments == {}
    worker_pool.execute_coach.assert_not_called()


# match runner

@pytest.mark.asyncio
async def test_execute_tick_runs_coaches_and_clears_triggers(match, monkeypatch):
    monkeypatch.setattr(
        "app.game.match_runner.match_connection_manager.broadcast",
        MagicMock(side_effect=lambda *args: _async_none()),
    )

    coordinator = MagicMock()
    coordinator.get_actions.return_value = {}
    coordinator.get_coach_assignments.return_value = {1: [(1, "Defender")]}

    engine = MagicMock()
    engine.step.side_effect = lambda match, snapshot, actions: (
        match.pending_coach_triggers.append((1, CoachTrigger.GOAL_FOR))
    )

    runner = MatchRunner(coordinator, engine)

    await runner.execute_tick(match)

    coordinator.get_coach_assignments.assert_called_once_with(
        match,
        [(1, CoachTrigger.GOAL_FOR)],
    )
    assert match.pending_coach_triggers == []
    assert match.participation_a.pending_coach_assignments == [(1, "Defender")]


@pytest.mark.asyncio
async def test_execute_tick_without_triggers_does_not_run_coaches(match, monkeypatch):
    monkeypatch.setattr(
        "app.game.match_runner.match_connection_manager.broadcast",
        MagicMock(side_effect=lambda *args: _async_none()),
    )

    coordinator = MagicMock()
    coordinator.get_actions.return_value = {}

    runner = MatchRunner(coordinator, MagicMock())

    await runner.execute_tick(match)

    coordinator.get_coach_assignments.assert_not_called()


@pytest.mark.asyncio
async def test_run_match_runs_coaches_for_the_first_period(match, monkeypatch):
    monkeypatch.setattr(
        "app.game.match_runner.match_connection_manager.broadcast",
        MagicMock(side_effect=lambda *args: _async_none()),
    )
    monkeypatch.setattr(
        "app.game.match_runner.match_connection_manager.close_match_connection",
        MagicMock(side_effect=lambda *args: _async_none()),
    )
    monkeypatch.setattr("app.game.match_runner.TIC_DURATION", 0)

    match.state = MatchState.NOT_STARTED
    match.duration_ticks = 1

    coordinator = MagicMock()
    coordinator.get_actions.return_value = {}
    coordinator.get_coach_assignments.return_value = {}

    runner = MatchRunner(coordinator, MagicMock())

    await runner.run_match(match)

    first_call = coordinator.get_coach_assignments.call_args_list[0]

    assert first_call.args[1] == [
        (match.participation_a.club_id, CoachTrigger.PERIOD_START),
        (match.participation_b.club_id, CoachTrigger.PERIOD_START),
    ]


async def _async_none():
    return None


# validation and application of behavior changes

def test_apply_coach_assignments_discards_invalid_ones(match):
    match.participation_a.pending_coach_assignments = [
        (1, "Defender"),    # valid
        (7, "Defender"),    # rival
        (4, "Defender"),    # substitute
        (2, "Goalkeeper"),  # unknown behavior name
        (99, "Defender"),   # unknown player
    ]

    applied = match.apply_pending_behavior_changes()

    assert applied == {1: [(1, "Defender")], 2: []}
    assert match.participation_a.get_player(1).current_behavior_id == 2
    assert match.participation_a.get_player(2).current_behavior_id == 1
    assert match.participation_a.get_player(4).current_behavior_id is None
    assert match.participation_b.get_player(7).current_behavior_id == 1


def test_apply_pending_changes_empties_queues(match):
    match.participation_a.pending_coach_assignments = [(1, "Defender")]
    match.participation_a.plan_behavior_change(2, 2)

    match.apply_pending_behavior_changes()

    assert match.participation_a.pending_coach_assignments == []
    assert match.participation_a.pending_behavior_changes == {}


def test_manual_change_wins_over_coach_in_the_same_tick(match):
    match.participation_a.pending_coach_assignments = [(1, "Defender")]
    match.participation_a.plan_behavior_change(1, 1)

    applied = match.apply_pending_behavior_changes()

    assert match.participation_a.get_player(1).current_behavior_id == 1
    assert applied[1] == []


def test_manual_change_is_discarded_if_player_left_the_field(match):
    match.participation_a.plan_behavior_change(1, 2)
    match.participation_a.get_player(1).is_on_field = False

    match.apply_pending_behavior_changes()

    assert match.participation_a.get_player(1).current_behavior_id == 1


def test_last_coach_assignment_for_a_player_wins(match):
    match.participation_a.pending_coach_assignments = [
        (1, "Defender"),
        (1, "Attacker"),
    ]

    match.apply_pending_behavior_changes()

    assert match.participation_a.get_player(1).current_behavior_id == 1


@pytest.mark.asyncio
async def test_execute_tick_applies_pending_changes_before_behaviors(match, monkeypatch):
    monkeypatch.setattr(
        "app.game.match_runner.match_connection_manager.broadcast",
        MagicMock(side_effect=lambda *args: _async_none()),
    )

    match.participation_a.pending_coach_assignments = [(1, "Defender")]

    coordinator = MagicMock()
    coordinator.get_actions.return_value = {}

    runner = MatchRunner(coordinator, MagicMock())

    await runner.execute_tick(match)

    snapshot = coordinator.get_actions.call_args.args[0]

    assert snapshot.players_a[0].current_behavior_id == 2


# websocket

def test_build_coach_changes_message():
    message = build_coach_changes_message(
        {
            1: [(1, "Defender")],
            2: [],
        },
        from_tic=5,
    )

    assert message.model_dump() == {
        "event": "coach_changes",
        "from_tic": 5,
        "changes": [
            {"club_id": 1, "player_id": 1, "behavior": "Defender"},
        ],
    }


@pytest.mark.asyncio
async def test_execute_tick_broadcasts_applied_coach_changes(match, monkeypatch):
    broadcast = MagicMock(side_effect=lambda *args: _async_none())
    monkeypatch.setattr(
        "app.game.match_runner.match_connection_manager.broadcast",
        broadcast,
    )

    match.participation_a.pending_coach_assignments = [
        (1, "Defender"),
        (7, "Defender"),  # rival, discarded
    ]

    coordinator = MagicMock()
    coordinator.get_actions.return_value = {}

    runner = MatchRunner(coordinator, MagicMock())

    await runner.execute_tick(match)

    events = [call.args[1].event for call in broadcast.call_args_list]
    coach_message = broadcast.call_args_list[0].args[1]

    assert events == ["coach_changes", "estado_partido"]
    assert [change.player_id for change in coach_message.changes] == [1]


@pytest.mark.asyncio
async def test_execute_tick_does_not_broadcast_coach_changes_without_changes(match, monkeypatch):
    broadcast = MagicMock(side_effect=lambda *args: _async_none())
    monkeypatch.setattr(
        "app.game.match_runner.match_connection_manager.broadcast",
        broadcast,
    )

    # the only coach assignment is overwritten by the manual change
    match.participation_a.pending_coach_assignments = [(1, "Defender")]
    match.participation_a.plan_behavior_change(1, 1)

    coordinator = MagicMock()
    coordinator.get_actions.return_value = {}

    runner = MatchRunner(coordinator, MagicMock())

    await runner.execute_tick(match)

    events = [call.args[1].event for call in broadcast.call_args_list]

    assert events == ["estado_partido"]
