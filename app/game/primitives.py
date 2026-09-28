"""
Behavior API primitives and helpers available to player behaviors.
"""

from math import hypot
from .types import Direction, Position


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