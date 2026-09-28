"""
Behavior API primitives and helpers available to player behaviors.
"""

from math import hypot

from .constants import TIC_DURATION
from .context import get_current_context
from .types import Direction, Position, PlayerState, BallState, Period

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

    return get_current_context().teammates


def opponents() -> list[PlayerState]:
    """
    Return the states of the current player's opponents.
        
    Returns:
        Opponents' ids and positions.
    """

    return get_current_context().opponents


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
    if distance < 0:
        raise ValueError("Distance cannot be negative.")
    
    context = get_current_context()
    max_speed = context.max_move_speed

    # Convert maximum speed (m/s) into the maximum distance
    # the player can travel during one simulation tic.
    max_distance = max_speed * TIC_DURATION

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
    if distance < 0:
        raise ValueError("Distance cannot be negative.")
    
    context = get_current_context()
    max_speed = context.max_move_speed

    # Convert maximum speed (m/s) into the maximum distance
    # the player can travel during one simulation tic.
    max_distance = max_speed * TIC_DURATION

    # Normalize the requested distance against the maximum reachable distance.
    factor = distance / max_distance

    # Values above 1.0 mean the distance cannot be fully covered in one tic,
    # so the maximum available speed factor is returned.
    return min(factor, 1.0)



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