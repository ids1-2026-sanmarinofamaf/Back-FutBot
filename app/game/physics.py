"""Physics calculations used by the game simulation."""

from .types import Direction, Velocity


def calculate_max_move_distance(max_move_speed: float) -> float:
    raise NotImplementedError


def calculate_speed_factor(
    max_move_speed: float,
    distance: float
) -> float:
    raise NotImplementedError


def calculate_kick_travel_distance(
    ball_velocity: Velocity,
    kick_direction: Direction,
    kick_speed: float
) -> float:
    raise NotImplementedError


def calculate_kick_force_factor(
    ball_velocity: Velocity,
    kick_direction: Direction,
    max_distance_speed: float,
    distance: float
) -> float:
    raise NotImplementedError