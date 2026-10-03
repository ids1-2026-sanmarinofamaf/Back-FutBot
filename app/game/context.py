"""
Execution context used during behavior play() execution
and exposed to Behavior API primitives.
"""

from contextvars import ContextVar
from dataclasses import dataclass

from .types import BallState, PlayerState, Position, Period, Side


@dataclass
class BehaviorContext:
    player: PlayerState
    teammates: list[PlayerState]
    opponents: list[PlayerState]
    ball: BallState

    my_team_score: int
    opponent_score: int

    starting_position: Position

    current_period: Period
    side: Side
    match_time_remaining: float
    period_time_remaining: float

    control_range: float
    tics_until_kick: int
    max_move_speed: float
    max_kick_force: float


# Context-local storage for the BehaviorContext of the current play() execution.
# It is kept private so the rest of the application only interacts through
# get_current_context(), set_current_context(), and clear_current_context().
_current_context: ContextVar[BehaviorContext | None] = ContextVar(
    "behavior_context",
    default=None,
)


def get_current_context() -> BehaviorContext:
    """
    Return the BehaviorContext associated with the current play() execution.

    Returns:
        Current BehaviorContext.

    Raises:
        RuntimeError: If no BehaviorContext is currently set.
    """
    context = _current_context.get()

    if context is None:
        raise RuntimeError("Behavior context is not set")

    return context


def set_current_context(context: BehaviorContext) -> None:
    """
    Set the BehaviorContext for the current play() execution.

    Args:
        context: BehaviorContext to make available to Behavior API primitives.
    """
    _current_context.set(context)


def clear_current_context() -> None:
    """
    Clear the BehaviorContext associated with the current play() execution.
    """
    _current_context.set(None)