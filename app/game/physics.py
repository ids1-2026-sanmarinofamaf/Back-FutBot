"""Physics calculations used by the game simulation."""

from math import hypot, isclose, sqrt
from typing import Callable

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
    TIC_DURATION,
    MAX_BALL_SPEED,
    MIN_BALL_DECELERATION,
    MAX_BALL_DECELERATION,
    KICK_INERTIA_FACTOR,
    BALL_STOP_THRESHOLD,
    COLLISION_PENALTY,
)


def distance(from_position: Position, to_position: Position) -> float:
    """
    Return the distance between two positions.

    Args:
        from_position: origin position.
        to_position: destination position.
    Returns:
        Distance between the two positions.
    """
    # Calculates the difference along each axis to use as input for hypot().
    delta_x = to_position[0] - from_position[0]
    delta_y = to_position[1] - from_position[1]

    # Hypot(x,y) calculates the Euclidean distance between x and y
    return hypot(delta_x, delta_y)


def direction_to(from_position: Position, to_position: Position) -> Direction:
    """
    Return a unit direction vector from the origin position to the target position.

    Args:
        from_position: origin position.
        to_position: target position.
    Returns:
        Unit direction vector to the target.
    Raises:
        ValueError: If both position are identical.
    """
    distance_to_target = distance(from_position, to_position)
    # Handle error when from_position = to_position
    if distance_to_target == 0.0:
        raise ValueError("Cannot calculate direction between identical positions.")
    
    # Calculates the difference along each axis to use to normalize vector.
    delta_x = to_position[0] - from_position[0]
    delta_y = to_position[1] - from_position[1]

    # Return the normalize vector
    return (
        delta_x/distance_to_target, 
        delta_y/distance_to_target
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
    """
    Calculate the estimated distance the ball will travel after a kick.

    The estimate considers the ball's current velocity in the kick direction,
    the applied kick force, and an average deceleration between the initial
    deceleration and the minimum ball deceleration.

    Args:
        ball_velocity: Ball velocity before the kick.
        kick_direction: Unit vector representing the kick direction.
        kick_force: Effective kick force applied to the ball.

    Returns:
        Estimated travel distance of the ball in meters.
    """
    validate_direction(kick_direction)

    initial_speed = _kick_initial_speed(
        ball_velocity,
        kick_direction,
        kick_force,
    )

    if initial_speed == 0.0:
        return 0.0

    initial_deceleration = _ball_deceleration(initial_speed)

    # As the ball slows down, its deceleration approaches the minimum.
    # We use the average as a simple approximation for the whole trajectory.
    average_deceleration = (
        initial_deceleration + MIN_BALL_DECELERATION
    ) / 2

    # From v² = (v0² -vf²) + 2ad, with final velocity equal to BALL_STOP_THRESHOLD
    return (
        initial_speed**2 - BALL_STOP_THRESHOLD**2
    ) / (2 * average_deceleration)
    

def calculate_kick_force_factor(
    ball_velocity: Velocity,
    kick_direction: Direction,
    kick_force: float,
    distance: float
) -> float:
    """
    Calculate the kick force factor required to reach a target distance.

    Args:
        ball_velocity: Ball velocity before the kick.
        kick_direction: Unit vector representing the kick direction.
        max_kick_force: Player's maximum effective kick force.
        distance: Target travel distance in meters.

    Returns:
        Kick force factor in the range [0.0, 1.0]. Returns 1.0 if the
        requested distance cannot be reached with the available kick force.

    Raises:
        ValueError: If distance is negative or max_kick_force is not positive.
    """
    validate_distance(distance)
    validate_direction(kick_direction)

    if kick_force <= 0:
        raise ValueError(f"Fuerza maxima invalida: {kick_force}")

    if distance == 0:
        return 0.0

    max_distance = calculate_kick_travel_distance(
        ball_velocity,
        kick_direction,
        kick_force,
    )

    if distance >= max_distance:
        return 1.0

    low = 0.0
    high = 1.0

    # Binary search to found the smallest factor which reach the target
    for _ in range(12):
        middle = (low + high) / 2

        test_force = kick_force * middle

        travel_distance = calculate_kick_travel_distance(
            ball_velocity,
            kick_direction,
            test_force,
        )

        if travel_distance < distance:
            low = middle
        else:
            high = middle

    return high


def calculate_ball_state_after(
    ball_state: BallState,
    duration: float,
) -> BallState:
    """
    Calculate the ball state after a given duration while applying
    deceleration.

    Args:
        ball_state: Current ball position and velocity.
        duration: Time interval in seconds.

    Returns:
        Ball position and velocity after the given duration.
    """
    position, velocity = ball_state

    speed = _vector_magnitude(velocity)

    if speed <= BALL_STOP_THRESHOLD:
        return (
            position,
            (0.0, 0.0),
        )

    deceleration = _ball_deceleration(speed)

    # v1 = max(v0 - a * Δt, 0)
    next_speed = max(
        speed - deceleration * duration,
        0.0,
    )

    if next_speed <= BALL_STOP_THRESHOLD:
        next_speed = 0.0

    # Unit vector in the current movement direction.
    direction = (
        velocity[0] / speed,
        velocity[1] / speed,
    )

    # v_avg = (v0 + v1) / 2
    average_speed = (
        speed + next_speed
    ) / 2

    # ΔP = direction * v_avg * Δt
    displacement = (
        average_speed * duration
    )

    next_position = (
        position[0] + direction[0] * displacement,
        position[1] + direction[1] * displacement,
    )

    # V1 = direction * v1
    next_velocity = (
        direction[0] * next_speed,
        direction[1] * next_speed,
    )

    return (
        next_position,
        next_velocity,
    )


def calculate_ball_next_state(
    ball_state: BallState,
) -> BallState:
    """
    Calculate the ball state after one simulation tic.
    """
    return calculate_ball_state_after(
        ball_state,
        TIC_DURATION,
    )


def calculate_ball_next_position(ball_state: BallState) -> Position:
    """
    Calculate the ball position after one tic.

    The displacement is estimated using the average speed between the
    beginning and the end of the tic while preserving the current
    direction of movement.

    Args:
        ball_state: Current ball position and velocity.

    Returns:
        Predicted ball position after one tic.
    """
    next_position, _ = calculate_ball_next_state(
        ball_state
    )

    return next_position


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


def effective_physical_value(
    pacss: int,
    collision_penalty_remaining: int,
    converter: Callable[[int], float],
) -> float:
    max_value = converter(pacss)

    return(
        max_value * COLLISION_PENALTY
        if collision_penalty_remaining > 0
        else max_value
    )


def collision_time(
    start_a: Position,
    end_a: Position,
    radius_a: float,
    start_b: Position,
    end_b: Position,
    radius_b: float,
) -> float | None:
    """
    Return the first normalized time in [0, 1] at which two moving
    circular objects collide.

    Returns:
        First collision time in [0, 1], or None if no collision occurs.
    """
    relative_start = (
        start_a[0] - start_b[0],
        start_a[1] - start_b[1],
    )

    movement_a = _displacement(start_a, end_a)
    movement_b = _displacement(start_b, end_b)

    relative_movement = (
        movement_a[0] - movement_b[0],
        movement_a[1] - movement_b[1],
    )

    collision_distance = radius_a + radius_b

    # |R0 + Vt|² = (ra + rb)²
    # => at² + bt + c = 0
    a = _vector_magnitude(relative_movement) ** 2
    b = 2 * _dot_product(relative_start, relative_movement)
    c = (
        _vector_magnitude(relative_start) ** 2
        - collision_distance ** 2
    )

    # R0 · V < 0 -> approaching
    if c <= 0:
        if _dot_product(relative_start, relative_movement) < 0:
            return 0.0

        return None

    if isclose(a, 0.0):
        return None

    # Δ = b² - 4ac
    discriminant = b ** 2 - 4 * a * c

    if discriminant < 0:
        return None

    # t = (-b - √Δ) / 2a
    first_collision = (
        -b - sqrt(discriminant)
    ) / (2 * a)

    if 0.0 <= first_collision <= 1.0:
        return first_collision

    return None


def position_at_time(
    start: Position,
    end: Position,
    time: float,
) -> Position:
    """
    Return the position along a linear trajectory at normalized time [0, 1].
    """
    # P(t) = P0 + t(P1 - P0)
    return (
        start[0] + time * (end[0] - start[0]),
        start[1] + time * (end[1] - start[1]),
    )


def calculate_kick_velocity(
    ball_velocity: Velocity,
    kick_direction: Direction,
    kick_force: float,
) -> Velocity:
    """
    Calculate the ball velocity immediately after a kick.

    Formula:
        V = direction * speed
    """
    speed = _kick_initial_speed(
        ball_velocity,
        kick_direction,
        kick_force,
    )

    return (
        kick_direction[0] * speed,
        kick_direction[1] * speed,
    )


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

    # Normalize PACSS to [0,1]
    n = (pacss - 20) / 80

    # Smoothstep
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


def _displacement(
    from_position: Position,
    to_position: Position,
) -> tuple[float, float]:
    """
    Return the displacement vector from one position to another.

    Formula:
        ΔP = P1 - P0
    """
    return (
        to_position[0] - from_position[0],
        to_position[1] - from_position[1],
    )


def _dot_product(
    vector_a: tuple[float, float],
    vector_b: tuple[float, float],
) -> float:
    """
    Calculate the dot product between two 2D vectors.

    Formula:
        a · b = ax * bx + ay * by
    """
    return (
        vector_a[0] * vector_b[0]
        + vector_a[1] * vector_b[1]
    )


def _vector_magnitude(vector: tuple[float, float]) -> float:
    """
    Calculate the magnitude of a 2D vector.

    Formula:
        |v| = sqrt(vx² + vy²)
    """
    return sqrt(vector[0] ** 2 + vector[1] ** 2)


def _ball_deceleration(speed: float) -> float:
    """
    Calculate the ball deceleration based on its current speed.

    Args:
        speed: Current ball speed in meters per second.

    Returns:
        Ball deceleration in meters per second squared.

    Raises:
        ValueError: If speed is negative or exceeds MAX_BALL_SPEED.
    """
    if not 0.0 <= speed <= MAX_BALL_SPEED:
        raise ValueError(f"Velocidad de pelota invalida: {speed}")

    # Normalize speed to [0, 1].
    n = speed / MAX_BALL_SPEED

    # Smoothstep
    smooth = 3 * n**2 - 2 * n**3

    return (
        MIN_BALL_DECELERATION
        + smooth * (MAX_BALL_DECELERATION - MIN_BALL_DECELERATION)
    )


def _kick_initial_speed(
    ball_velocity: Velocity,
    kick_direction: Direction,
    kick_force: float,
) -> float:
    """
    Calculate the ball's initial speed in the kick direction after a kick.

    Args:
        ball_velocity: Ball velocity before the kick.
        kick_direction: Unit vector representing the kick direction.
        kick_force: Effective kick force applied to the ball.

    Returns:
        Initial ball speed after the kick, limited by MAX_BALL_SPEED.

    Raises:
        ValueError: If kick_force is negative.
    """
    if kick_force < 0:
        raise ValueError(f"Fuerza de pateo invalida: {kick_force}")

    # Velocity aligned with kick
    parallel_velocity = _dot_product(
        ball_velocity,
        kick_direction,
    )

    # Kick conserved some ball inertia 
    inherited_velocity = parallel_velocity * KICK_INERTIA_FACTOR

    # Velocity cannot be negative or faster than MAX_BALL_SPEED
    return min(
        max(kick_force + inherited_velocity, 0.0),
        MAX_BALL_SPEED,
    )
