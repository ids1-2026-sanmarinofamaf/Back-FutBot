"""
Unit tests for Behavior API primitives and helper functions.
"""

import pytest

from app.game.primitives import (
    distance, 
    direction_to
)


def test_distance_between_two_points():
    assert distance((0.0, 0.0), (3.0, 4.0)) == 5.0


def test_distance_between_same_position():
    assert distance((2.0, 3.0), (2.0, 3.0)) == 0.0


def test_direction_to_right():
    assert direction_to((0.0, 0.0), (3.0, 0.0)) == (1.0, 0.0)


def test_direction_to_down():
    assert direction_to((0.0, 5.0), (0.0, 2.0)) == (0.0, -1.0)


def test_direction_to_diagonal():
    assert direction_to((0.0, 0.0), (3.0, 4.0)) == (0.6, 0.8)


def test_direction_to_same_position_raises_error():
    with pytest.raises(ValueError):
        direction_to((2.0, 2.0), (2.0, 2.0))