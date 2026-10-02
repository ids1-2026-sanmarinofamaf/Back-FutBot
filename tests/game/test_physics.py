"""
Unit tests for game physics and related calculations.
"""

import pytest
from math import isclose, sqrt

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
    MAX_KICK_COOLDOWN_TICS,
    TIC_DURATION,
    BALL_STOP_THRESHOLD,
    KICK_INERTIA_FACTOR,
    MAX_BALL_SPEED,
)
from app.game.physics import (
    _smoothstep,
    max_move_speed,
    max_kick_force,
    control_range,
    kick_cooldown_tics,
    calculate_max_move_distance,
    calculate_speed_factor,
    calculate_kick_travel_distance,
    calculate_kick_force_factor,
    calculate_ball_next_position,
    calculate_kick_velocity,
    calculate_ball_next_state,
)


def test_smoothstep_returns_zero_for_minimum_pacss():
    assert _smoothstep(MIN_PACSS) == 0.0
    

def test_smoothstep_returns_half_for_middle_pacss():
    assert _smoothstep((MAX_PACSS + MIN_PACSS) / 2) == 0.5


def test_smoothstep_returns_one_for_maximum_pacss():
    assert _smoothstep(MAX_PACSS) == 1.0


@pytest.mark.parametrize(
    "invalid_pacss",
    [
        MIN_PACSS - 1,
        MAX_PACSS + 1,
    ],
)
def test_smoothstep_raises_value_error_for_invalid_pacss(invalid_pacss):
    with pytest.raises(ValueError):
        _smoothstep(invalid_pacss)


def test_max_move_speed_returns_minimum_speed_for_minimum_pacss():
    assert max_move_speed(MIN_PACSS) == MIN_MOVE_SPEED


def test_max_move_speed_returns_middle_speed_for_middle_pacss():
    pacss = (MIN_PACSS + MAX_PACSS) / 2
    speed = max_move_speed(pacss)

    expected = (MIN_MOVE_SPEED + MAX_MOVE_SPEED) / 2

    assert isclose(speed, expected)


def test_max_move_speed_returns_maximum_speed_for_maximum_pacss():
    assert max_move_speed(MAX_PACSS) == MAX_MOVE_SPEED

@pytest.mark.parametrize(
    "invalid_pacss",
    [
        MIN_PACSS - 1,
        MAX_PACSS + 1,
    ],
)
def test_max_move_speed_raises_value_error_for_invalid_pacss(invalid_pacss):
    with pytest.raises(ValueError):
        max_move_speed(invalid_pacss)


def test_max_kick_force_returns_minimum_force_for_minimum_pacss():
    assert max_kick_force(MIN_PACSS) == MIN_KICK_FORCE


def test_max_kick_power_returns_middle_force_for_middle_pacss():
    pacss = (MIN_PACSS + MAX_PACSS) / 2
    force = max_kick_force(pacss)

    expected = (MIN_KICK_FORCE + MAX_KICK_FORCE) / 2

    assert isclose(force, expected)


def test_max_kick_force_returns_maximum_force_for_maximum_pacss():
    assert max_kick_force(MAX_PACSS) == MAX_KICK_FORCE


@pytest.mark.parametrize(
    "invalid_pacss",
    [
        MIN_PACSS - 1,
        MAX_PACSS + 1,
    ],
)
def test_max_kick_force_raises_value_error_for_invalid_pacss(invalid_pacss):
    with pytest.raises(ValueError):
        max_kick_force(invalid_pacss)


def test_control_range_returns_minimum_range_for_minimum_pacss():
    assert control_range(MIN_PACSS) == MIN_CONTROL_RANGE


def test_control_range_returns_middle_range_for_middle_pacss():
    pacss = (MIN_PACSS + MAX_PACSS) / 2
    control = control_range(pacss)

    expected = (MIN_CONTROL_RANGE + MAX_CONTROL_RANGE) / 2

    assert isclose(control, expected)


def test_control_range_returns_maximum_range_for_maximum_pacss():
    assert control_range(MAX_PACSS) == MAX_CONTROL_RANGE


@pytest.mark.parametrize(
    "invalid_pacss",
    [
        MIN_PACSS - 0.1,
        MAX_PACSS + 0.1,
    ],
)
def test_control_range_raises_value_error_for_invalid_pacss(
    invalid_pacss
):
    with pytest.raises(ValueError):
        control_range(invalid_pacss)


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


def test_calculate_max_move_distance_returns_distance_for_minimum_speed():
    expected = MIN_MOVE_SPEED * TIC_DURATION

    assert isclose(
        calculate_max_move_distance(MIN_MOVE_SPEED),
        expected
    )


def test_calculate_max_move_distance_returns_distance_for_maximum_speed():
    expected = MAX_MOVE_SPEED * TIC_DURATION

    assert isclose(
        calculate_max_move_distance(MAX_MOVE_SPEED),
        expected
    )


@pytest.mark.parametrize(
    "invalid_speed",
    [
        MIN_MOVE_SPEED - 1,
        MAX_MOVE_SPEED + 1,
    ],
)
def test_calculate_max_move_distance_raises_value_error_for_invalid_speed(
    invalid_speed
):
    with pytest.raises(ValueError):
        calculate_max_move_distance(invalid_speed)


def test_calculate_speed_factor_returns_zero_for_zero_distance():
    assert calculate_speed_factor(MIN_MOVE_SPEED, 0.0) == 0.0


def test_calculate_speed_factor_returns_half_for_half_max_distance():
    max_distance = calculate_max_move_distance(MAX_MOVE_SPEED)
    distance = max_distance / 2

    factor = calculate_speed_factor(MAX_MOVE_SPEED, distance)

    assert isclose(factor, 0.5)


def test_calculate_speed_factor_returns_one_for_max_distance():
    max_distance = calculate_max_move_distance(MAX_MOVE_SPEED)

    factor = calculate_speed_factor(MAX_MOVE_SPEED, max_distance)

    assert isclose(factor, 1.0)


def test_calculate_speed_factor_returns_one_when_distance_exceeds_maximum():
    max_distance = calculate_max_move_distance(MAX_MOVE_SPEED)

    factor = calculate_speed_factor(
        MAX_MOVE_SPEED,
        max_distance * 2
    )

    assert isclose(factor, 1.0)


def test_calculate_speed_factor_raises_value_error_for_negative_distance():
    with pytest.raises(ValueError):
        calculate_speed_factor(MAX_MOVE_SPEED, -1.0)


@pytest.mark.parametrize(
    "invalid_speed",
    [
        MIN_MOVE_SPEED - 0.1,
        MAX_MOVE_SPEED + 0.1,
    ],
)
def test_calculate_speed_factor_raises_value_error_for_invalid_speed(
    invalid_speed
):
    with pytest.raises(ValueError):
        calculate_speed_factor(invalid_speed, 1.0)


def test_calculate_kick_travel_distance_returns_zero_when_initial_speed_is_below_stop_threshold():
    distance = calculate_kick_travel_distance(
        ball_velocity=(0.0, 0.0),
        kick_direction=(1.0, 0.0),
        kick_force=0.0,
    )

    assert distance == 0.0


def test_calculate_kick_travel_distance_increases_with_kick_force():
    low_force_distance = calculate_kick_travel_distance(
        ball_velocity=(0.0, 0.0),
        kick_direction=(1.0, 0.0),
        kick_force=10.0,
    )

    high_force_distance = calculate_kick_travel_distance(
        ball_velocity=(0.0, 0.0),
        kick_direction=(1.0, 0.0),
        kick_force=20.0,
    )

    assert high_force_distance > low_force_distance


def test_calculate_kick_travel_distance_uses_ball_inertia_in_kick_direction():
    without_inertia = calculate_kick_travel_distance(
        ball_velocity=(0.0, 0.0),
        kick_direction=(1.0, 0.0),
        kick_force=20.0,
    )

    with_inertia = calculate_kick_travel_distance(
        ball_velocity=(10.0, 0.0),
        kick_direction=(1.0, 0.0),
        kick_force=20.0,
    )

    assert with_inertia > without_inertia


def test_calculate_kick_travel_distance_reduces_distance_when_ball_moves_against_kick():
    without_inertia = calculate_kick_travel_distance(
        ball_velocity=(0.0, 0.0),
        kick_direction=(1.0, 0.0),
        kick_force=20.0,
    )

    against_inertia = calculate_kick_travel_distance(
        ball_velocity=(-10.0, 0.0),
        kick_direction=(1.0, 0.0),
        kick_force=20.0,
    )

    assert against_inertia < without_inertia


def test_calculate_kick_force_factor_returns_zero_for_zero_distance():
    factor = calculate_kick_force_factor(
        ball_velocity=(0.0, 0.0),
        kick_direction=(1.0, 0.0),
        kick_force=20.0,
        distance=0.0,
    )

    assert factor == 0.0


def test_calculate_kick_force_factor_returns_one_when_distance_exceeds_maximum():
    max_distance = calculate_kick_travel_distance(
        ball_velocity=(0.0, 0.0),
        kick_direction=(1.0, 0.0),
        kick_force=20.0,
    )

    factor = calculate_kick_force_factor(
        ball_velocity=(0.0, 0.0),
        kick_direction=(1.0, 0.0),
        kick_force=20.0,
        distance=max_distance + 1.0,
    )

    assert factor == 1.0


def test_calculate_kick_force_factor_returns_factor_that_reaches_target_distance():
    target_distance = 20.0

    factor = calculate_kick_force_factor(
        ball_velocity=(0.0, 0.0),
        kick_direction=(1.0, 0.0),
        kick_force=20.0,
        distance=target_distance,
    )

    actual_distance = calculate_kick_travel_distance(
        ball_velocity=(0.0, 0.0),
        kick_direction=(1.0, 0.0),
        kick_force=20.0 * factor,
    )

    assert actual_distance >= target_distance


def test_calculate_ball_next_position_returns_same_position_when_ball_is_stopped():
    ball_state = (
        (10.0, 5.0),
        (0.0, 0.0),
    )

    assert calculate_ball_next_position(ball_state) == (10.0, 5.0)


def test_calculate_ball_next_position_returns_same_position_below_stop_threshold():
    ball_state = (
        (10.0, 5.0),
        (BALL_STOP_THRESHOLD / 2, 0.0),
    )

    assert calculate_ball_next_position(ball_state) == (10.0, 5.0)


def test_calculate_ball_next_position_moves_ball_in_x_direction():
    position = (0.0, 0.0)
    velocity = (10.0, 0.0)

    next_position = calculate_ball_next_position(
        (position, velocity)
    )

    assert next_position[0] > position[0]
    assert isclose(next_position[1], position[1])


def test_calculate_ball_next_position_moves_ball_in_y_direction():
    position = (0.0, 0.0)
    velocity = (0.0, 10.0)

    next_position = calculate_ball_next_position(
        (position, velocity)
    )

    assert isclose(next_position[0], position[0])
    assert next_position[1] > position[1]


def test_calculate_ball_next_position_preserves_movement_direction():
    position = (0.0, 0.0)
    velocity = (3.0, 4.0)

    next_position = calculate_ball_next_position(
        (position, velocity)
    )

    displacement_x = next_position[0] - position[0]
    displacement_y = next_position[1] - position[1]

    assert isclose(
        displacement_y / displacement_x,
        4.0 / 3.0,
    )


def test_calculate_kick_velocity_applies_direction():
    velocity = calculate_kick_velocity(
        ball_velocity=(0.0, 0.0),
        kick_direction=(1.0, 0.0),
        kick_force=20.0,
    )

    assert velocity == pytest.approx((20.0, 0.0))


def test_calculate_kick_velocity_preserves_direction_components():
    direction = (
        1 / sqrt(2),
        1 / sqrt(2),
    )

    velocity = calculate_kick_velocity(
        ball_velocity=(0.0, 0.0),
        kick_direction=direction,
        kick_force=20.0,
    )

    expected_component = 20.0 / sqrt(2)

    assert velocity == pytest.approx(
        (
            expected_component,
            expected_component,
        )
    )


def test_calculate_kick_velocity_inherits_parallel_ball_velocity():
    velocity = calculate_kick_velocity(
        ball_velocity=(10.0, 0.0),
        kick_direction=(1.0, 0.0),
        kick_force=20.0,
    )

    expected_speed = (
        20.0
        + 10.0 * KICK_INERTIA_FACTOR
    )

    assert velocity == pytest.approx(
        (expected_speed, 0.0)
    )


def test_calculate_kick_velocity_ignores_perpendicular_ball_velocity():
    velocity = calculate_kick_velocity(
        ball_velocity=(0.0, 10.0),
        kick_direction=(1.0, 0.0),
        kick_force=20.0,
    )

    assert velocity == pytest.approx(
        (20.0, 0.0)
    )


def test_calculate_kick_velocity_is_limited_by_max_ball_speed():
    velocity = calculate_kick_velocity(
        ball_velocity=(MAX_BALL_SPEED, 0.0),
        kick_direction=(1.0, 0.0),
        kick_force=MAX_BALL_SPEED,
    )

    assert velocity == pytest.approx(
        (MAX_BALL_SPEED, 0.0)
    )


def test_calculate_ball_next_state_keeps_stopped_ball_still():
    ball_state = (
        (20.0, 10.0),
        (0.0, 0.0),
    )

    next_state = calculate_ball_next_state(ball_state)

    assert next_state == (
        (20.0, 10.0),
        (0.0, 0.0),
    )


def test_calculate_ball_next_state_moves_ball_forward():
    ball_state = (
        (20.0, 10.0),
        (10.0, 0.0),
    )

    next_position, next_velocity = calculate_ball_next_state(
        ball_state
    )

    assert next_position[0] > 20.0
    assert next_position[1] == pytest.approx(10.0)

    assert next_velocity[0] < 10.0
    assert next_velocity[0] > 0.0
    assert next_velocity[1] == pytest.approx(0.0)


def test_calculate_ball_next_state_preserves_direction():
    ball_state = (
        (20.0, 10.0),
        (6.0, 8.0),
    )

    _, next_velocity = calculate_ball_next_state(
        ball_state
    )

    original_ratio = 6.0 / 8.0
    next_ratio = next_velocity[0] / next_velocity[1]

    assert next_ratio == pytest.approx(original_ratio)


def test_calculate_ball_next_state_stops_below_threshold():
    ball_state = (
        (20.0, 10.0),
        (BALL_STOP_THRESHOLD, 0.0),
    )

    next_state = calculate_ball_next_state(ball_state)

    assert next_state == (
        (20.0, 10.0),
        (0.0, 0.0),
    )