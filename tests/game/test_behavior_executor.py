"""
Unit tests for runtime behavior execution.
"""

import pytest

from app.game.behavior_executor import (
    execute_behavior_strict,
    InvalidBehaviorAction,
)
from app.game.models.actions import MoveAction, KickAction, WaitAction
from app.game.context import get_current_context
from app.game.primitives import move
from app.game.models.runtime_behavior import RuntimeBehavior

def test_execute_behavior_strict_returns_move_action(
    context,
    move_behavior,
):
    action = execute_behavior_strict(context, move_behavior)

    assert isinstance(action, MoveAction)
    assert action.move_direction == (1.0, 0.0)
    assert action.move_speed_factor == 1.0


def test_execute_behavior_strict_returns_kick_action(
    context,
    kick_behavior,
):
    action = execute_behavior_strict(context, kick_behavior)

    assert isinstance(action, KickAction)


def test_execute_behavior_strict_returns_wait_action(
    context,
    wait_behavior,
):
    action = execute_behavior_strict(context, wait_behavior)

    assert isinstance(action, WaitAction)


def test_execute_behavior_strict_clears_context_after_successful_execution(
    context,
    kick_behavior,
):
    execute_behavior_strict(context, kick_behavior)

    with pytest.raises(
        RuntimeError,
        match="Behavior context is not set"
    ):
        get_current_context()


def invalid_move_play():
    return move(
        direction=(1.0, 0.0),
        speed_factor=1.5,
    )


def test_execute_behavior_strict_rejects_invalid_move_parameters(
    context,
):
    behavior = RuntimeBehavior(
        id=99,
        play=invalid_move_play,
    )

    with pytest.raises(ValueError):
        execute_behavior_strict(
            context,
            behavior,
        )


def test_execute_behavior_strict_accepts_voluntary_wait(
    context,
    wait_behavior,
):
    action = execute_behavior_strict(
        context,
        wait_behavior,
    )

    assert isinstance(action, WaitAction)


def test_execute_behavior_strict_propagates_execution_error(
    context,
    failing_behavior,
):
    with pytest.raises(RuntimeError, match="Behavior execution failed"):
        execute_behavior_strict(
            context,
            failing_behavior,
        )


def test_execute_behavior_strict_rejects_invalid_action(
    context,
    invalid_behavior,
):
    with pytest.raises(InvalidBehaviorAction):
        execute_behavior_strict(
            context,
            invalid_behavior,
        )


def test_execute_behavior_strict_clears_context_after_error(
    context,
    failing_behavior,
):
    with pytest.raises(RuntimeError):
        execute_behavior_strict(
            context,
            failing_behavior,
        )

    with pytest.raises(
        RuntimeError,
        match="Behavior context is not set",
    ):
        get_current_context()
