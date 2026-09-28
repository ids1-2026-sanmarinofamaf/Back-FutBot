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