"""
Behavior execution utilities.

This module is responsible for executing a runtime behavior within a
BehaviorContext, validating the action returned by play(), and ensuring
that the execution context is always cleared after execution.
"""

from app.game.models.runtime_behavior import RuntimeBehavior, RuntimeCoachBehavior
from app.game.models.actions import MoveAction, KickAction, WaitAction
from app.game.types import Assignment
from app.game.context import (
    BehaviorContext,
    CoachContext,
    set_current_context,
    clear_current_context,
    )

Action = MoveAction | KickAction | WaitAction

def execute_behavior(
        context: BehaviorContext,
        behavior: RuntimeBehavior,
) -> Action:
    """
    Execute a runtime behavior within the given BehaviorContext.

    Args:
        context: Execution context available to Behavior API primitives.
        behavior: Runtime behavior whose play() function will be executed.

    Returns:
        Action returned by play(), or WaitAction if execution fails or
        returns an invalid action.
    """
    set_current_context(context)

    try:
        action = behavior.play()

        if not isinstance(action, (MoveAction, KickAction, WaitAction)):
            return WaitAction()

        return action
    except Exception:
        return WaitAction()
    
    finally:
        clear_current_context()


def execute_coach_behavior(
        context: CoachContext,
        behavior: RuntimeCoachBehavior,
) -> list[Assignment]:
    """
    Execute a runtime coach behavior within the given CoachContext.

    Args:
        context: Execution context available to the coach primitives.
        behavior: Runtime coach behavior whose coach() function will be executed.

    Returns:
        Assignments returned by coach(). Elements that are not a
        (player_id, behavior_name) pair are discarded. If execution fails
        or coach() does not return a list, an empty list is returned.
    """
    set_current_context(context)

    try:
        assignments = behavior.coach()

        if not isinstance(assignments, list):
            return []

        return [
            assignment
            for assignment in assignments
            if _is_assignment(assignment)
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
