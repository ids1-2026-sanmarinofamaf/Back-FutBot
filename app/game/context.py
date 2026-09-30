"""Execution context available to Behavior API primitives."""

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


def get_current_context() -> BehaviorContext:
    raise NotImplementedError


def set_current_context(context: BehaviorContext) -> None:
    raise NotImplementedError


def clear_current_context() -> None:
    raise NotImplementedError