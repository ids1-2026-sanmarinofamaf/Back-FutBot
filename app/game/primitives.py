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