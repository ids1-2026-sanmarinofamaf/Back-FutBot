"""Domain models and actions used by the game simulation."""

from dataclasses import dataclass

from .types import Direction


@dataclass(frozen=True)
class MoveAction:
    """
    Represent a movement action requested by a BOT player.

    Attributes:
        move_direction: Direction in which the player should move.
        move_speed_factor: Fraction of the player's maximum movement speed.
    """
    move_direction: Direction
    move_speed_factor: float


@dataclass(frozen=True)
class KickAction:
    """
    Represent a kick action requested by a BOT player.

    Attributes:
        kick_direction: Direction in which the player should kick.
        kick_force_factor: Fraction of the player's maximum kick force.
    """
    kick_direction: Direction
    kick_force_factor: float


@dataclass(frozen=True)
class WaitAction:
    """
    Represent an action where the BOT player performs no voluntary action.
    """
    pass