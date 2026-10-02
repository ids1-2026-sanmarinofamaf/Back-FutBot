"""
Behavior API primitives and helpers available to player behaviors.
"""

from math import hypot

from .constants import LEFT_GOAL, RIGHT_GOAL
from .models.actions import MoveAction, KickAction, WaitAction
from .context import get_current_context
from .types import Direction, Position, PlayerState, BallState, Period, Side
from .physics import(
    calculate_max_move_distance,
    calculate_speed_factor,
    calculate_kick_travel_distance,
    calculate_kick_force_factor,
    calculate_ball_next_position,
    validate_distance,
    validate_direction,
    validate_factor,
    distance as physics_distance,
    direction_to as physics_direction_to
)

def self() -> PlayerState:
    """
    Return the current BOT player's state.

    Returns:
        Current BOT player's id and position.
    """

    return get_current_context().player


def teammates() -> list[PlayerState]:
    """
    Return the states of the current player's teammates.
    
    Returns:
        Teammates' ids and positions.
    """

    return list(get_current_context().teammates)


def opponents() -> list[PlayerState]:
    """
    Return the states of the current player's opponents.
        
    Returns:
        Opponents' ids and positions.
    """

    return list(get_current_context().opponents)


def ball() -> BallState:
    """
    Return the state of the ball.
            
    Returns:
        Ball position and velocity.
    """

    return get_current_context().ball


def score() -> tuple[int, int]:
    """
    Return the current score of the match.
            
    Returns:
        Current player's team score and opponent team score.
    """
    context = get_current_context()

    return (
        context.my_team_score,
        context.opponent_score,
    )


def match_time_remaining() -> float:
    """
    Return the remaining match time.

    Returns:
        Remaining match time in seconds.
    """

    return get_current_context().match_time_remaining


def current_period() -> Period:
    """
    Return the current match period.

    Returns:
        Current period of the match.
    """

    return get_current_context().current_period


def period_time_remaining() -> float:
    """
    Return the remaining time of the current period.

    Returns:
        Remaining period time in seconds.
    """

    return get_current_context().period_time_remaining


def starting_position() -> Position:
    """
    Return the current BOT player's starting position.

    Returns:
        Starting position of the current player.
    """

    return get_current_context().starting_position


def own_goal() -> Position:
    """
    Return the center position of the current player's own goal.

    Returns:
        Center position of the current player's own goal.
    """
    context = get_current_context()

    return LEFT_GOAL if context.side == Side.LEFT else RIGHT_GOAL


def opponent_goal() -> Position:
    """
    Return the center position of the current player's opponent's goal.

    Returns:
        Center position of the current player's opponent's goal.
    """
    context = get_current_context()

    return RIGHT_GOAL if context.side == Side.LEFT else LEFT_GOAL


def can_kick() -> bool:
    """
    Return whether the current BOT player can attempt to kick the ball.

    Returns:
        True if the ball is within control range and the kick cooldown is zero.
        False otherwise.
    """
    context = get_current_context()
    player_position = context.player[1]
    ball_position = context.ball[0]
    cooldown = tics_until_kick()
    control_distance = control_range()

    # Check whether the ball is close enough for the player to interact with it.
    ball_in_range = distance(ball_position, player_position) <= control_distance

    # The player can kick only if the ball is in range and
    # the kick cooldown has completely finished.    
    return ball_in_range and cooldown == 0


def tics_until_kick() -> int:
    """
    Return the numbers of tics until the BOT player can kick the ball again.

    Returns:
        Numbers of tics remaining until the BOT player can kick again.
    """

    return get_current_context().tics_until_kick


def control_range() -> float:
    """
    Return the maximum distance at which the BOT player can control the ball.
    Returns:
        Maximum ball control distance for the current BOT player.
    """

    return get_current_context().control_range


def can_move_distance(distance: float) -> bool:
    """
    Return whether the current BOT player can travel a given distance
    during the next tic.

    Args:
        distance: Distance to travel.

    Returns:
        True if the player can travel the complete distance in one tic.
        False otherwise.

    Raises:
        ValueError: If distance is negative.
    """
    validate_distance(distance)
    
    context = get_current_context()
    max_speed = context.max_move_speed
    max_distance = calculate_max_move_distance(max_speed)

    return distance <= max_distance


def speed_for_distance(distance: float) -> float:
    """
    Return the movement speed factor required to travel a given distance
    during the next tic.

    Args:
        distance: Distance to travel.

    Returns:
        Speed factor between 0.0 and 1.0.

    Raises:
        ValueError: If distance is negative.
    """
    validate_distance(distance)
    
    context = get_current_context()
    max_speed = context.max_move_speed

    return calculate_speed_factor(max_speed, distance)


def can_kick_distance(direction: Direction, distance: float) -> bool:
    """
    Return whether the current BOT player can make the ball travel
    a given distance with a single kick in the specified direction.

    Args:
        direction: Direction in which the ball would be kicked.
        distance: Distance the ball should travel.

    Returns:
        True if the ball can reach the requested distance with one kick.
        False otherwise.

    Raises:
        ValueError: If distance is negative.
        ValueError: If direction is not a valid unit vector.
    """
    validate_distance(distance)
    validate_direction(direction)

    context = get_current_context()
    ball_velocity = context.ball[1]
    max_kick_force = context.max_kick_force

    max_kick_distance = calculate_kick_travel_distance(
            ball_velocity,
            direction,
            max_kick_force
        )

    return distance <= max_kick_distance    


def kick_force_for_distance(direction: Direction, distance: float) -> float:
    """
    Return the kick force factor required to make the ball travel
    approximately a given distance in the specified direction.

    Args:
        direction: Direction in which the ball would be kicked.
        distance: Distance the ball should travel.

    Returns:
        Kick force factor between 0.0 and 1.0.

    Raises:
        ValueError: If distance is negative.
        ValueError: If direction is not a valid unit vector.
    """
    validate_distance(distance)
    validate_direction(direction)

    context = get_current_context()
    ball_velocity = context.ball[1]
    max_kick_force = context.max_kick_force

    return calculate_kick_force_factor(
        ball_velocity,
        direction,
        max_kick_force,
        distance
    )


def move(direction: Direction, speed_factor: float) -> MoveAction:
    """
    Create a movement action for the current BOT player.

    Args:
        direction: Direction in which the player should move.
        speed_factor: Fraction of the player's maximum movement speed,
            between 0.0 and 1.0.

    Returns:
        MoveAction containing the requested movement direction and speed factor.

    Raises:
        ValueError: If direction is not a valid unit vector.
        ValueError: If speed_factor is outside the interval [0.0, 1.0].
    """
    validate_direction(direction)
    validate_factor(speed_factor)

    return MoveAction(
        move_direction=direction,
        move_speed_factor=speed_factor
    )

def kick(direction: Direction, force_factor: float) -> KickAction:
    """
    Create a kick action for the current BOT player.

    Args:
        direction: Direction in which the player should kick.
        force_factor: Fraction of the player's maximum kick force,
            between 0.0 and 1.0.

    Returns:
        KickAction containing the requested movement direction and force factor.

    Raises:
        ValueError: If direction is not a valid unit vector.
        ValueError: If force_factor is outside the interval [0.0, 1.0].
    """
    validate_direction(direction)
    validate_factor(force_factor)

    return KickAction(
        kick_direction=direction,
        kick_force_factor=force_factor
    )


def wait() -> WaitAction:
    """
    Create a wait action for the current BOT player.

    Returns:
        WaitAction representing no voluntary action for the next tic.
    """
    return WaitAction()    


def distance(from_position: Position, to_position: Position) -> float:
    """
    Return the distance between two positions.

    Args:
        from_position: origin position.
        to_position: destination position.
    Returns:
        Distance between the two positions.
    """
    return physics_distance(
        from_position,
        to_position,
    )


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
    return physics_direction_to(
        from_position, 
        to_position,
    )

def next_ball_position() -> Position:
    """
    Return the estimated position of the ball during the next tic.

    Returns:
        Estimated ball position for the next tic according to the
        current ball state and the game physics.
    """
    context = get_current_context()
    ball_state = context.ball

    return calculate_ball_next_position(ball_state)