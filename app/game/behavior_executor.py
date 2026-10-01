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
    