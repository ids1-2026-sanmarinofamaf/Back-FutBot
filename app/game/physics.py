"""Physics calculations used by the game simulation."""

from .types import Direction, Velocity, Position, BallState
from .constants import (
    MIN_MOVE_SPEED,
    MAX_MOVE_SPEED,
    MIN_KICK_FORCE,
    MAX_KICK_FORCE,
    MIN_CONTROL_RANGE,
    MAX_CONTROL_RANGE,
    MIN_KICK_COOLDOWN_TICS,
    MAX_KICK_COOLDOWN_TICS,
)

def max_move_speed(speed: int) -> float:
    """
    Convert a SPEED PACSS value into the player's maximum movement speed.

    Args:
        speed: SPEED attribute in the range [20, 100].

    Returns:
        Maximum movement speed in meters per second.

    Raises:
        ValueError: If speed is outside the valid PACSS range.
    """
    return _interpolate_pacss(
        speed,
        MIN_MOVE_SPEED,
        MAX_MOVE_SPEED
    )


def max_kick_force(power: int) -> float:
    """
    Convert a POWER PACSS value into the player's maximum kick force.

    Args:
        power: POWER attribute in the range [20, 100].

    Returns:
        Maximum kick force available to the player.

    Raises:
        ValueError: If power is outside the valid PACSS range.
    """
    return _interpolate_pacss(
        power,
        MIN_KICK_FORCE,
        MAX_KICK_FORCE
    )


def control_range(control: int) -> float:
    """
    Convert a CONTROL PACSS value into the player's ball control range.

    Args:
        control: CONTROL attribute in the range [20, 100].

    Returns:
        Ball control range in meters.

    Raises:
        ValueError: If control is outside the valid PACSS range.
    """
    return _interpolate_pacss(
        control,
        MIN_CONTROL_RANGE,
        MAX_CONTROL_RANGE
    )


def kick_cooldown_tics(agility: int) -> int:
    """
    Convert an AGILITY PACSS value into the number of tics required
    before the player can kick again.

    Higher AGILITY values produce shorter cooldowns.

    Args:
        agility: AGILITY attribute in the range [20, 100].

    Returns:
        Kick cooldown measured in tics.

    Raises:
        ValueError: If agility is outside the valid PACSS range.
    """
    return round(
        _interpolate_pacss(
            agility,
            MAX_KICK_COOLDOWN_TICS,
            MIN_KICK_COOLDOWN_TICS
        )
    )


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
    kick_force: float
) -> float:
    raise NotImplementedError


def calculate_kick_force_factor(
    ball_velocity: Velocity,
    kick_direction: Direction,
    kick_force: float,
    distance: float
) -> float:
    raise NotImplementedError


def calculate_ball_next_position(ball_state: BallState) -> Position:
    raise NotImplementedError


def _validate_pacss(pacss: int) -> None:
    """
    Validate that a PACSS attribute is within the valid range.

    Raises:
        ValueError: If value is outside [20, 100].
    """
    if not 20 <= pacss <= 100:
        raise ValueError(f"Valor PACSS invalido: {pacss}")


def _smoothstep(pacss: int) -> float:
    """
    Normalize a valid PACSS value and apply the smoothstep curve.

    Args:
        pacss: PACSS attribute in the range [20, 100].

    Returns:
        Smoothstep interpolation factor in the range [0.0, 1.0].
    """
    _validate_pacss(pacss)

    # Convertimos el PACSS de [20, 100] a [0,1]
    n = (pacss - 20) / 80
    # Calculamos smoothstep
    smooth = 3 * n**2 - 2 * n**3

    return smooth


def _interpolate_pacss(
    pacss: int,
    minimum: float,
    maximum: float
) -> float:
    """
    Convert a PACSS value into a physical value between the given bounds.

    Args:
        pacss: PACSS attribute in the range [20, 100].
        minimum: Physical value corresponding to PACSS 20.
        maximum: Physical value corresponding to PACSS 100.

    Returns:
        Interpolated physical value.
    """

    return minimum + _smoothstep(pacss) * (maximum - minimum)