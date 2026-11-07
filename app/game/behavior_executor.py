"""
Behavior execution utilities.

This module is responsible for executing a runtime behavior within a
BehaviorContext, validating the action returned by play(), and ensuring
that the execution context is always cleared after execution.
"""

from app.game.models.runtime_behavior import RuntimeBehavior, RuntimeCoachBehavior
from app.game.models.actions import MoveAction, KickAction, WaitAction
from app.game.types import CoachCommand, Substitution
from app.game.context import (
    BehaviorContext,
    CoachContext,
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


def execute_coach_behavior(
        context: CoachContext,
        behavior: RuntimeCoachBehavior,
) -> list[CoachCommand]:
    """
    Execute a runtime coach behavior within the given CoachContext.

    Args:
        context: Execution context available to the coach primitives.
        behavior: Runtime coach behavior whose coach() function will be executed.

    Returns:
        Assignments and substitutions returned by coach(). Any other element
        is discarded. If execution fails or coach() does not return a list,
        an empty list is returned.
    """
    set_current_context(context)

    try:
        commands = behavior.coach()

        if not isinstance(commands, list):
            return []

        return [
            command
            for command in commands
            if _is_assignment(command) or isinstance(command, Substitution)
        ]
    except Exception:
        return []

    finally:
        clear_current_context()


def _is_assignment(value: object) -> bool:
    return (
        isinstance(value, tuple)
        and len(value) == 2
        and isinstance(value[0], int)
        and not isinstance(value[0], bool)
        and isinstance(value[1], str)
    )
