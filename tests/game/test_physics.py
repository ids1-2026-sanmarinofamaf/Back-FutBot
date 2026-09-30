"""
Unit tests for game physics and related calculations.
"""

import pytest
from math import isclose

from app.game.constants import (
    MIN_PACSS,
    MAX_PACSS,
    MIN_MOVE_SPEED,
    MAX_MOVE_SPEED,
    MIN_KICK_FORCE,
    MAX_KICK_FORCE,
    MIN_CONTROL_RANGE,
    MAX_CONTROL_RANGE,
    MIN_KICK_COOLDOWN_TICS,
    MAX_KICK_COOLDOWN_TICS
)
from app.game.physics import (
    _smoothstep,
    max_move_speed,
    max_kick_force,
    control_range,
    kick_cooldown_tics
)

def test_smoothstep_returns_zero_for_minimum_pacss():
    assert _smoothstep(MIN_PACSS) == 0.0
    

def test_smoothstep_returns_half_for_middle_pacss():
    assert _smoothstep((MAX_PACSS + MIN_PACSS) / 2) == 0.5


def test_smoothstep_returns_one_for_maximum_pacss():
    assert _smoothstep(MAX_PACSS) == 1.0


def test_smoothstep_raises_value_error_below_minimum_pacss():
    with pytest.raises(ValueError):
        _smoothstep(MIN_PACSS - 1)


def test_smoothstep_raises_value_error_above_maximum_pacss():
    with pytest.raises(ValueError):
        _smoothstep(MAX_PACSS + 1)


def test_max_move_speed_returns_minimum_speed_for_minimum_pacss():
    assert max_move_speed(MIN_PACSS) == MIN_MOVE_SPEED


def test_max_move_speed_returns_middle_speed_for_middle_pacss():
    pacss = (MIN_PACSS + MAX_PACSS) / 2
    speed = max_move_speed(pacss)

    expected = (MIN_MOVE_SPEED + MAX_MOVE_SPEED) / 2

    assert isclose(speed, expected)


def test_max_move_speed_returns_maximum_speed_for_maximum_pacss():
    assert max_move_speed(MAX_PACSS) == MAX_MOVE_SPEED


def test_max_move_speed_raises_value_error_for_invalid_pacss():
    with pytest.raises(ValueError):
        max_move_speed( MAX_PACSS + 1)


def test_max_kick_force_returns_minimum_force_for_minimum_pacss():
    assert max_kick_force(MIN_PACSS) == MIN_KICK_FORCE


def test_max_kick_power_returns_middle_force_for_middle_pacss():
    pacss = (MIN_PACSS + MAX_PACSS) / 2
    force = max_kick_force(pacss)

    expected = (MIN_KICK_FORCE + MAX_KICK_FORCE) / 2

    assert isclose(force, expected)


def test_max_kick_force_returns_maximum_force_for_maximum_pacss():
    assert max_kick_force(MAX_PACSS) == MAX_KICK_FORCE


def test_max_kick_force_raises_value_error_for_invalid_pacss():
    with pytest.raises(ValueError):
        max_kick_force( MAX_PACSS + 1)


def test_control_range_returns_minimum_range_for_minimum_pacss():
    assert control_range(MIN_PACSS) == MIN_CONTROL_RANGE


def test_control_range_returns_middle_range_for_middle_pacss():
    pacss = (MIN_PACSS + MAX_PACSS) / 2
    control = control_range(pacss)

    expected = (MIN_CONTROL_RANGE + MAX_CONTROL_RANGE) / 2

    assert isclose(control, expected)


def test_control_range_returns_maximum_range_for_maximum_pacss():
    assert control_range(MAX_PACSS) == MAX_CONTROL_RANGE


def test_control_range_raises_value_error_for_invalid_pacss():
    with pytest.raises(ValueError):
        control_range(MAX_PACSS + 1)


def test_kick_cooldown_returns_maximum_cooldown_for_minimum_pacss():
    assert kick_cooldown_tics(MIN_PACSS) == MAX_KICK_COOLDOWN_TICS


def test_kick_cooldown_returns_middle_cooldown_for_middle_pacss():
    pacss = (MIN_PACSS + MAX_PACSS) / 2
    cooldown = kick_cooldown_tics(pacss)

    expected = round(
        (MAX_KICK_COOLDOWN_TICS + MIN_KICK_COOLDOWN_TICS) / 2
    )

    assert cooldown == expected


def test_kick_cooldown_returns_minimum_cooldown_for_maximum_pacss():
    assert kick_cooldown_tics(MAX_PACSS) == MIN_KICK_COOLDOWN_TICS


def test_kick_cooldown_raises_value_error_for_invalid_pacss():
    with pytest.raises(ValueError):
        kick_cooldown_tics(MAX_PACSS + 1)