"""
Unit tests for Behavior API primitives and helper functions.
"""

import pytest
from unittest.mock import patch

from app.game.context import BehaviorContext
from app.game.types import Period
from app.game.primitives import (
    self,
    teammates,
    opponents,
    ball,
    score,
    match_time_remaining,
    current_period,
    period_time_remaining,
    starting_position,
    can_kick,
    tics_until_kick,
    control_range,
    can_move_distance,
    speed_for_distance,
    can_kick_distance,
    kick_force_for_distance,
    distance, 
    direction_to
)


@pytest.fixture
def context():
    return BehaviorContext(
        player=(1, (5.0, 4.0),),
        teammates=[
            (2, (6.0, 4.0)),
            (3, (7.0, 5.0)),
        ],
        opponents=[
            (4, (10.0, 8.0)),
            (5, (11.0, 6.0)),
            (6, (12.0, 4.0)),
        ],
        ball=((7.0, 5.0), (1.0, 0.0),),
        my_team_score=1,
        opponent_score=0,
        starting_position=(3.0, 3.0),
        current_period=Period.FIRST_QUARTER,
        match_time_remaining=120.0,
        period_time_remaining=30.0,
        control_range=0.8,
        tics_until_kick=0,
        max_move_speed=8.0,
        max_kick_force=20.0,
    )


@patch("app.game.primitives.get_current_context")
def test_self_returns_current_player(mock_get_current_context, context):
    mock_get_current_context.return_value = context

    assert self() == (1, (5.0, 4.0))


@patch("app.game.primitives.get_current_context")
def test_teammates_returns_current_player_teammates(
    mock_get_current_context,
    context
    ):
    mock_get_current_context.return_value = context

    assert teammates() == [(2, (6.0, 4.0)), (3, (7.0, 5.0)),]


@patch("app.game.primitives.get_current_context")
def test_opponents_returns_current_player_opponents(
    mock_get_current_context,
    context
    ):
    mock_get_current_context.return_value = context

    assert opponents() == [(4, (10.0, 8.0)), (5, (11.0, 6.0)), (6, (12.0, 4.0)),]


@patch("app.game.primitives.get_current_context")
def test_ball_returns_current_ball_state(mock_get_current_context, context):
    mock_get_current_context.return_value = context

    assert ball() == ((7.0, 5.0), (1.0, 0.0))


@patch("app.game.primitives.get_current_context")
def test_score_returns_current_match_score(
    mock_get_current_context, 
    context
    ):
    mock_get_current_context.return_value = context

    assert score() == (1, 0,)


@patch("app.game.primitives.get_current_context")
def test_match_time_remaining_returns_remaining_match_time(
    mock_get_current_context, 
    context
):
    mock_get_current_context.return_value = context

    assert match_time_remaining() == 120.0


@patch("app.game.primitives.get_current_context")
def test_current_period_returns_current_match_period(
    mock_get_current_context, 
    context
):
    mock_get_current_context.return_value = context

    assert current_period() == Period.FIRST_QUARTER


@patch("app.game.primitives.get_current_context")
def test_period_time_remaining_returns_remaining_period_time(
    mock_get_current_context, 
    context
):
    mock_get_current_context.return_value = context

    assert period_time_remaining() == 30.0


@patch("app.game.primitives.get_current_context")
def test_starting_position_returns_current_player_starting_position(
    mock_get_current_context, 
    context
):
    mock_get_current_context.return_value = context

    assert starting_position() == (3.0, 3.0)


@patch("app.game.primitives.get_current_context")
def test_tics_until_kick_returns_remaining_tics(
    mock_get_current_context, 
    context
):
    mock_get_current_context.return_value = context

    assert tics_until_kick() == 0


@patch("app.game.primitives.get_current_context")
def test_control_range_returns_current_player_range_control(
    mock_get_current_context, 
    context
):
    mock_get_current_context.return_value = context

    assert control_range() == 0.8


@patch("app.game.primitives.get_current_context")
def test_can_kick_returns_true_when_ball_is_in_range_and_cooldown_is_zero(
    mock_get_current_context,
    context
):
    # Ball is within control range and kick cooldown is zero.
    context.player = (1, (5.0, 4.0))
    context.ball = ((5.3, 4.0), (0.0, 0.0))
    context.control_range = 0.5
    context.tics_until_kick = 0
    mock_get_current_context.return_value = context

    assert can_kick() is True


@patch("app.game.primitives.get_current_context")
def test_can_kick_returns_false_when_ball_is_out_of_range(
    mock_get_current_context,
    context
):
    # Ball is outside the control range and kick cooldown is zero.
    context.player = (1, (5.0, 4.0))
    context.ball = ((10.0, 10.0), (0.0, 0.0))
    context.control_range = 0.5
    context.tics_until_kick = 0
    mock_get_current_context.return_value = context

    assert can_kick() is False


@patch("app.game.primitives.get_current_context")
def test_can_kick_returns_false_when_cooldown_is_not_zero(
    mock_get_current_context,
    context
):
    # Ball is within control range and kick cooldown is not zero.
    context.player = (1, (5.0, 4.0))
    context.ball = ((5.3, 4.0), (0.0, 0.0))
    context.control_range = 0.5
    context.tics_until_kick = 2
    mock_get_current_context.return_value = context

    assert can_kick() is False


@patch("app.game.primitives.get_current_context")
def test_can_kick_returns_true_when_ball_is_exactly_at_control_range(
    mock_get_current_context,
    context
):
    # Ball is exactly at control range and kick cooldown is zero.
    context.player = (1, (5.0, 4.0))
    context.ball = ((5.5, 4.0), (0.0, 0.0))
    context.control_range = 0.5
    context.tics_until_kick = 0
    mock_get_current_context.return_value = context

    assert can_kick() is True


def test_can_move_distance_raises_error_for_negative_distance():
    with pytest.raises(ValueError):
        can_move_distance(-2.0)


@patch("app.game.primitives.calculate_max_move_distance")
@patch("app.game.primitives.get_current_context")
def test_can_move_distance_returns_true_below_max_distance(
    mock_get_current_context,
    mock_calculate_max_move_distance,
    context
):
    mock_get_current_context.return_value = context
    mock_calculate_max_move_distance.return_value = 0.8

    assert can_move_distance(0.4) is True

    mock_calculate_max_move_distance.assert_called_once_with(
        context.max_move_speed
    )


@patch("app.game.primitives.calculate_max_move_distance")
@patch("app.game.primitives.get_current_context")
def test_can_move_distance_returns_true_at_max_distance(
    mock_get_current_context,
    mock_calculate_max_move_distance,
    context
):
    mock_get_current_context.return_value = context
    mock_calculate_max_move_distance.return_value = 0.8

    assert can_move_distance(0.8) is True


@patch("app.game.primitives.calculate_max_move_distance")
@patch("app.game.primitives.get_current_context")
def test_can_move_distance_returns_false_above_max_distance(
    mock_get_current_context,
    mock_calculate_max_move_distance,
    context
):
    mock_get_current_context.return_value = context
    mock_calculate_max_move_distance.return_value = 0.8

    assert can_move_distance(1.0) is False


def test_speed_for_distance_raises_error_for_negative_distance():
    with pytest.raises(ValueError):
        speed_for_distance(-2.0)


@patch("app.game.primitives.calculate_speed_factor")
@patch("app.game.primitives.get_current_context")
def test_speed_for_distance_returns_proportional_factor(
    mock_get_current_context,
    mock_calculate_speed_factor,
    context
):
    mock_get_current_context.return_value = context
    mock_calculate_speed_factor.return_value = 0.5

    assert speed_for_distance(0.4) == 0.5

    mock_calculate_speed_factor.assert_called_once_with(
        context.max_move_speed,
        0.4
    )


def test_can_kick_distance_raises_error_for_negative_distance():
    with pytest.raises(ValueError):
        can_kick_distance((1.0, 0.0), -0.1)


def test_can_kick_distance_raises_error_for_invalid_direction():
    with pytest.raises(ValueError):
        can_kick_distance((2.0, 0.0), 3.0)


@patch("app.game.primitives.calculate_kick_travel_distance")
@patch("app.game.primitives.get_current_context")
def test_can_kick_distance_returns_true_below_max_distance(
    mock_get_current_context,
    mock_calculate_kick_travel_distance,
    context,
):
    mock_get_current_context.return_value = context
    mock_calculate_kick_travel_distance.return_value = 10.0
    direction = (1.0, 0.0)

    assert can_kick_distance(direction, 8.0) is True

    mock_calculate_kick_travel_distance.assert_called_once_with(
        context.ball[1],
        direction,
        context.max_kick_force,
    )


@patch("app.game.primitives.calculate_kick_travel_distance")
@patch("app.game.primitives.get_current_context")
def test_can_kick_distance_returns_true_at_max_distance(
    mock_get_current_context,
    mock_calculate_kick_travel_distance,
    context,
):
    mock_get_current_context.return_value = context
    mock_calculate_kick_travel_distance.return_value = 10.0
    direction = (1.0, 0.0)

    assert can_kick_distance(direction, 10.0) is True


@patch("app.game.primitives.calculate_kick_travel_distance")
@patch("app.game.primitives.get_current_context")
def test_can_kick_distance_returns_false_above_max_distance(
    mock_get_current_context,
    mock_calculate_kick_travel_distance,
    context,
):
    mock_get_current_context.return_value = context
    mock_calculate_kick_travel_distance.return_value = 10.0
    direction = (1.0, 0.0)

    assert can_kick_distance(direction, 12.0) is False


def test_kick_force_for_distance_raises_error_for_negative_distance():
    with pytest.raises(ValueError):
        kick_force_for_distance((1.0, 0.0), -0.1)


def test_kick_force_for_distance_raises_error_for_invalid_direction():
    with pytest.raises(ValueError):
        kick_force_for_distance((0.0, 0.0), 5.0)


@patch("app.game.primitives.calculate_kick_force_factor")
@patch("app.game.primitives.get_current_context")
def test_kick_force_for_distance_returns_calculated_factor(
    mock_get_current_context,
    mock_calculate_kick_force_factor,
    context,
):
    mock_get_current_context.return_value = context
    mock_calculate_kick_force_factor.return_value = 0.5
    direction = (1.0, 0.0)

    assert kick_force_for_distance(direction, 8.0) == 0.5

    mock_calculate_kick_force_factor.assert_called_once_with(
        context.ball[1],
        direction,
        context.max_kick_force,
        8.0
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