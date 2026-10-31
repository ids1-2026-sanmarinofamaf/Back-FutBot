"""
Behavior execution utilities.

This module is responsible for executing a runtime behavior within a
BehaviorContext, validating the action returned by play(), and ensuring
that the execution context is always cleared after execution.
"""

from app.game.models.runtime_behavior import RuntimeBehavior
from app.game.models.actions import MoveAction, KickAction, WaitAction
from app.game.context import (
    BehaviorContext,
    set_current_context,
    clear_current_context,
    )


Action = MoveAction | KickAction | WaitAction


class InvalidBehaviorAction(Exception):
    """
    Raised when a behavior returns an invalid action.
    """


def execute_behavior_strict(
    context: BehaviorContext,
    behavior: RuntimeBehavior,
) -> Action:
    """
    Execute a behavior and propagate execution errors.

    Args:
        context: Execution context available to Behavior API primitives.
        behavior: Runtime behavior whose play() function will be executed.

    Returns:
        The valid action returned by play().

    Raises:
        InvalidBehaviorAction: If play() returns an invalid action.
        Exception: If play() raises an exception.
    """
    set_current_context(context)

    try:
        action = behavior.play()

        if not isinstance(action, Action):
            raise InvalidBehaviorAction(
                "Behavior returned an invalid action"
            )

        return action

    finally:
        clear_current_context()
