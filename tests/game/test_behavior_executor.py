"""
Unit tests for runtime behavior execution.
"""

import pytest

from app.game.behavior_executor import execute_behavior
from app.game.models.actions import MoveAction, KickAction, WaitAction
from app.game.context import get_current_context


def test_execute_behavior_returns_move_action(
    context,
    move_behavior,
):
    action = execute_behavior(context, move_behavior)

    assert isinstance(action, MoveAction)
    assert action.move_direction == (1.0, 0.0)
    assert action.move_speed_factor == 1.0


def test_execute_behavior_returns_kick_action(
    context,
    kick_behavior,
):
    action = execute_behavior(context, kick_behavior)

    assert isinstance(action, KickAction)


def test_execute_behavior_returns_wait_action(
    context,
    wait_behavior,
):
    action = execute_behavior(context, wait_behavior)

    assert isinstance(action, WaitAction)


def test_execute_behavior_returns_wait_action_for_invalid_result(
    context,
    invalid_behavior,
):
    action = execute_behavior(context, invalid_behavior)

    assert isinstance(action, WaitAction)


def test_execute_behavior_returns_wait_action_when_play_raises_exception(
    context,
    failing_behavior,
):
    action = execute_behavior(context, failing_behavior)

    assert isinstance(action, WaitAction)


def test_execute_behavior_clears_context_after_successful_execution(
    context,
    kick_behavior,
):
    execute_behavior(context, kick_behavior)

    with pytest.raises(
        RuntimeError,
        match="Behavior context is not set"
    ):
        get_current_context()
    

def test_execute_behavior_clears_context_after_failed_execution(
    context,
    failing_behavior
):
    execute_behavior(context, failing_behavior)

    with pytest.raises(
        RuntimeError,
        match="Behavior context is not set"
    ):
        get_current_context()