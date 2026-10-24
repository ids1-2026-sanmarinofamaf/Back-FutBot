from unittest.mock import MagicMock, patch

import pytest

from app.services.club_statistics_service import update_statistics


# club A wins
@patch(
    "app.services.club_statistics_service."
    "club_statistics_repository.increment_match_statistics"
)
def test_update_statistics_club_a_wins(mock_update):
    db = MagicMock()

    update_statistics(
        db=db,
        club_a_id=1,
        club_b_id=2,
        goals_a=3,
        goals_b=1,
    )

    assert mock_update.call_count == 2

    mock_update.assert_any_call(
        db=db,
        club_id=1,
        points=3,
        won=1,
        drawn=0,
        lost=0,
        goals_for=3,
        goals_against=1,
    )

    mock_update.assert_any_call(
        db=db,
        club_id=2,
        points=0,
        won=0,
        drawn=0,
        lost=1,
        goals_for=1,
        goals_against=3,
    )


# club B wins
@patch(
    "app.services.club_statistics_service."
    "club_statistics_repository.increment_match_statistics"
)
def test_update_statistics_club_b_wins(mock_update):
    db = MagicMock()

    update_statistics(
        db=db,
        club_a_id=1,
        club_b_id=2,
        goals_a=0,
        goals_b=2,
    )

    assert mock_update.call_count == 2

    mock_update.assert_any_call(
        db=db,
        club_id=1,
        points=0,
        won=0,
        drawn=0,
        lost=1,
        goals_for=0,
        goals_against=2,
    )

    mock_update.assert_any_call(
        db=db,
        club_id=2,
        points=3,
        won=1,
        drawn=0,
        lost=0,
        goals_for=2,
        goals_against=0,
    )


# draw
@patch(
    "app.services.club_statistics_service."
    "club_statistics_repository.increment_match_statistics"
)
def test_update_statistics_draw(mock_update):
    db = MagicMock()

    update_statistics(
        db=db,
        club_a_id=1,
        club_b_id=2,
        goals_a=2,
        goals_b=2,
    )

    assert mock_update.call_count == 2

    for club_id in (1, 2):
        mock_update.assert_any_call(
            db=db,
            club_id=club_id,
            points=1,
            won=0,
            drawn=1,
            lost=0,
            goals_for=2,
            goals_against=2,
        )

    db.commit.assert_not_called()