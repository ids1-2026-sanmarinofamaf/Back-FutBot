
from unittest.mock import MagicMock, patch
from app.models.league import LeaguePrivacy
import pytest
from types import SimpleNamespace
from app.services.club_statistics_service import update_statistics


# club A wins
@patch(
    "app.services.club_statistics_service."
    "club_statistics_repository.increment_match_statistics"
)
def test_update_statistics_club_a_wins(mock_update):
    db = MagicMock()
    league = SimpleNamespace(privacy=LeaguePrivacy.PUBLICA)

    update_statistics(
        db=db,
        league=league,
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
    league = SimpleNamespace(privacy=LeaguePrivacy.PUBLICA)

    update_statistics(
        db=db,
        league=league,
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
    league = SimpleNamespace(privacy=LeaguePrivacy.PUBLICA)

    update_statistics(
        db=db,
        league=league,
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

@patch(
    "app.services.club_statistics_service."
    "club_statistics_repository.increment_match_statistics"
)
def test_private_league_does_not_update_statistics(mock_update):
    db = MagicMock()
    league = MagicMock()
    league.privacy = LeaguePrivacy.PRIVADA

    update_statistics(
        db=db,
        league=league,
        club_a_id=1,
        club_b_id=2,
        goals_a=3,
        goals_b=1,
    )

    mock_update.assert_not_called()


@pytest.mark.parametrize("winner_club_id", [1, 2])
@patch(
    "app.services.club_statistics_service."
    "club_statistics_repository.increment_match_statistics"
)
def test_tiebreak_win_preserves_regulation_goals(
    mock_update,
    winner_club_id,
):
    db = MagicMock()
    league = SimpleNamespace(privacy=LeaguePrivacy.PUBLICA)
    loser_id = 2 if winner_club_id == 1 else 1

    update_statistics(
        db=db,
        league=league,
        club_a_id=1,
        club_b_id=2,
        goals_a=1,
        goals_b=1,
        winner_club_id=winner_club_id,
    )

    assert mock_update.call_count == 2

    mock_update.assert_any_call(
        db=db,
        club_id=winner_club_id,
        points=3,
        won=1,
        drawn=0,
        lost=0,
        goals_for=1,
        goals_against=1,
    )
    mock_update.assert_any_call(
        db=db,
        club_id=loser_id,
        points=0,
        won=0,
        drawn=0,
        lost=1,
        goals_for=1,
        goals_against=1,
    )

    db.commit.assert_not_called()


@pytest.mark.parametrize(
    ("goals_a", "goals_b", "winner_club_id", "message"),
    [
        (1, 1, 3, "participating club"),
        (2, 1, 2, "contradicts"),
        (1, 2, 1, "contradicts"),
    ],
)
@patch(
    "app.services.club_statistics_service."
    "club_statistics_repository.increment_match_statistics"
)
def test_invalid_winner_does_not_update_global_statistics(
    mock_update,
    goals_a,
    goals_b,
    winner_club_id,
    message,
):
    db = MagicMock()
    league = SimpleNamespace(privacy=LeaguePrivacy.PUBLICA)

    with pytest.raises(ValueError, match=message):
        update_statistics(
            db=db,
            league=league,
            club_a_id=1,
            club_b_id=2,
            goals_a=goals_a,
            goals_b=goals_b,
            winner_club_id=winner_club_id,
        )

    mock_update.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.parametrize("winner_club_id", [1, 2])
@patch(
    "app.services.club_statistics_service."
    "club_statistics_repository.increment_match_statistics"
)
def test_private_tiebreak_does_not_update_global_statistics(
    mock_update,
    winner_club_id,
):
    db = MagicMock()
    league = SimpleNamespace(privacy=LeaguePrivacy.PRIVADA)

    update_statistics(
        db=db,
        league=league,
        club_a_id=1,
        club_b_id=2,
        goals_a=1,
        goals_b=1,
        winner_club_id=winner_club_id,
    )

    mock_update.assert_not_called()
    db.commit.assert_not_called()
