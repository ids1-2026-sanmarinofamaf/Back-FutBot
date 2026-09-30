"""
Shared fixtures for game-related unit tests.
"""

import pytest

from app.game.context import BehaviorContext
from app.game.types import Period, Side


@pytest.fixture
def context():
    """
    Return a valid BehaviorContext for game-related unit tests.

    The fixture represents a known match state so tests can focus on the
    behavior being validated without rebuilding the execution context each time.
    """
    return BehaviorContext(
        player=(1, (5.0, 4.0)),
        teammates=[
            (2, (6.0, 4.0)),
            (3, (7.0, 5.0)),
        ],
        opponents=[
            (4, (10.0, 8.0)),
            (5, (11.0, 6.0)),
            (6, (12.0, 4.0)),
        ],
        ball=((7.0, 5.0), (1.0, 0.0)),
        my_team_score=1,
        opponent_score=0,
        starting_position=(3.0, 3.0),
        current_period=Period.FIRST_QUARTER,
        side=Side.LEFT,
        match_time_remaining=120.0,
        period_time_remaining=30.0,
        control_range=0.8,
        tics_until_kick=0,
        max_move_speed=8.0,
        max_kick_force=20.0,
    )

@pytest.fixture
def other_context():
    """
    Return a second valid BehaviorContext with different values.

    Used to verify that the current execution context can be replaced.
    """
    return BehaviorContext(
        player=(7, (15.0, 10.0)),
        teammates=[
            (8, (14.0, 9.0)),
            (9, (13.0, 8.0)),
        ],
        opponents=[
            (10, (4.0, 3.0)),
            (11, (5.0, 5.0)),
            (12, (6.0, 7.0)),
        ],
        ball=((12.0, 10.0), (-1.0, 0.5)),
        my_team_score=2,
        opponent_score=1,
        starting_position=(17.0, 10.0),
        current_period=Period.SECOND_QUARTER,
        side=Side.RIGHT,
        match_time_remaining=90.0,
        period_time_remaining=20.0,
        control_range=1.2,
        tics_until_kick=2,
        max_move_speed=9.5,
        max_kick_force=25.0,
    )