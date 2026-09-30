"""Physics calculations used by the game simulation."""

from math import hypot, isclose

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
    TIC_DURATION
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
    """
    Calculate the maximum distance a player can move during one tic.

    Args:
        max_move_speed: Player's maximum movement speed in meters per second.

    Returns:
        Maximum distance the player can travel during one tic, in meters.
    
    Raises:
        ValueError: If max_move_speed is outside the valid range.
    """
    if not MIN_MOVE_SPEED <= max_move_speed <= MAX_MOVE_SPEED :
        raise ValueError(f"Velocidad invalida: {max_move_speed}")

    return max_move_speed * TIC_DURATION


def calculate_speed_factor(
    max_move_speed: float,
    distance: float
) -> float:
    """
    Calculate the movement speed factor required to cover a distance in one tic.

    Args:
        max_move_speed: Player's maximum movement speed in meters per second.
        distance: Distance to cover in meters.

    Returns:
        Speed factor in the range [0.0, 1.0]. Returns 1.0 if the requested
        distance exceeds the maximum distance the player can cover in one tic.

    Raises:
        ValueError: If distance is negative or max_move_speed is not positive.
    """
    validate_distance(distance)

    if distance == 0:
        return 0.0

    return min(
        distance / calculate_max_move_distance(max_move_speed),
        1.0
    )

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


def validate_distance(distance: float) -> None:
    """
    Validate that a distance is non-negative.

    Args:
        distance: Distance value to validate.

    Raises:
        ValueError: If the distance is negative.
    """
    if distance < 0:
        raise ValueError("Distance cannot be negative.")


def validate_direction(direction: Direction) -> None:
    """
    Validate that a direction is a unit vector.

    Floating-point comparisons use a small tolerance to account for
    numerical precision errors.

    Args:
        direction: Direction vector to validate.

    Raises:
        ValueError: If the direction is not approximately a unit vector.
    """
    magnitude = hypot(direction[0], direction[1])

    if not isclose(
        magnitude,
        1.0,rel_tol=1e-9,
        abs_tol=1e-9
    ):
        raise ValueError("Direction must be a unit vector.")
    

def validate_factor(factor: float) -> None:
    """
    Validate that a factor belongs to the interval [0.0, 1.0].

    Args:
        factor: Factor to validate.

    Raises:
        ValueError: If the factor is outside the interval [0.0, 1.0].
    """
    if not 0.0 <= factor <= 1.0:
        raise ValueError("Factor must be between 0.0 and 1.0.")


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