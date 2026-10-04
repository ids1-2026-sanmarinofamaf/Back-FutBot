import pytest

from unittest.mock import MagicMock, patch

from app.schemas.friendly_game import FriendlyGameCreate
from app.services.friendly_game_service import create_friendly_game
from app.models.roster import Formation
from app.models.player_on_roster import RosterSlot
from app.models.friendly_game_participation import FriendlyGameRole

@pytest.fixture
def valid_friendly_game_data():
    data = MagicMock(spec=FriendlyGameCreate)
    data.duration = 1000

    data.roster = MagicMock()
    data.roster.formation = Formation.OFFENSIVE
    data.roster.players = [
        MagicMock(
            player_id=1,
            is_starter=True,
            slot=RosterSlot.LEFT,
            initial_behavior_id=10,
        ),
        MagicMock(
            player_id=2,
            is_starter=True,
            slot=RosterSlot.CENTER,
            initial_behavior_id=11,
        ),
        MagicMock(
            player_id=3,
            is_starter=True,
            slot=RosterSlot.RIGHT,
            initial_behavior_id=12,
        ),
        MagicMock(
            player_id=4,
            is_starter=False,
            slot=None,
            initial_behavior_id=None,
        ),
        MagicMock(
            player_id=5,
            is_starter=False,
            slot=None,
            initial_behavior_id=None,
        ),
        MagicMock(
            player_id=6,
            is_starter=False,
            slot=None,
            initial_behavior_id=None,
        ),
    ]

    return data


@patch("app.services.friendly_game_service.club_repository")
@patch("app.services.friendly_game_service.player_repository")
@patch("app.services.friendly_game_service.behavior_repository")
@patch("app.services.friendly_game_service.roster_repository")
@patch("app.services.friendly_game_service.friendly_game_repository")

def test_create_friendly_game_success(
    mock_friendly_game_repository,
    mock_roster_repository,
    mock_behavior_repository,
    mock_player_repository,
    mock_club_repository,
    valid_friendly_game_data,
):
    db = MagicMock()

    club = MagicMock()
    club.id = 1
    mock_club_repository.get_by_user_id.return_value = club

    player = MagicMock()
    player.club_id = 1
    mock_player_repository.get_by_id.return_value = player

    behavior = MagicMock()
    behavior.club_id = 1
    mock_behavior_repository.get_by_id.return_value = behavior

    def save_roster(_db, roster):
        roster.id = 20

    mock_roster_repository.save.side_effect = save_roster

    friendly_game = MagicMock()
    friendly_game.id = 30
    mock_friendly_game_repository.create.return_value = friendly_game

    result_game, result_roster = create_friendly_game(
        db=db,
        user_id=5,
        data=valid_friendly_game_data,
    )

    assert result_game.id == 30
    assert result_roster.id == 20

    mock_friendly_game_repository.create_participation.assert_called_once_with(
        db=db,
        friendly_game_id=30,
        club_id=1,
        roster_id=20,
        role=FriendlyGameRole.CREATOR,
    )

    db.commit.assert_called_once()
    db.rollback.assert_not_called()


@patch("app.services.friendly_game_service.club_repository")
@patch("app.services.friendly_game_service.player_repository")

def test_rejects_roster_with_player_from_another_club(
    mock_player_repository,
    mock_club_repository,
    valid_friendly_game_data,
):
    db = MagicMock()

    club = MagicMock()
    club.id = 1
    mock_club_repository.get_by_user_id.return_value = club

    player = MagicMock()
    player.club_id = 2
    mock_player_repository.get_by_id.return_value = player

    with pytest.raises(
        ValueError,
        match="Player does not belong to user's club",
    ):
        create_friendly_game(
            db=db,
            user_id=5,
            data=valid_friendly_game_data,
        )

    db.commit.assert_not_called()
    db.rollback.assert_called_once()


@patch("app.services.friendly_game_service.club_repository")
@patch("app.services.friendly_game_service.player_repository")
@patch("app.services.friendly_game_service.behavior_repository")

def test_rejects_roster_with_behavior_from_another_club(
    mock_behavior_repository,
    mock_player_repository,
    mock_club_repository,
    valid_friendly_game_data,
):

    db = MagicMock()

    club = MagicMock()
    club.id = 1
    mock_club_repository.get_by_user_id.return_value = club

    player = MagicMock()
    player.club_id = 1
    mock_player_repository.get_by_id.return_value = player

    behavior = MagicMock()
    behavior.club_id = 2
    behavior.is_default = False
    mock_behavior_repository.get_by_id.return_value = behavior

    with pytest.raises(
        ValueError,
        match="Behavior does not belong to user's club",
    ):
        create_friendly_game(
            db=db,
            user_id=5,
            data=valid_friendly_game_data,
        )

    db.commit.assert_not_called()
    db.rollback.assert_called_once()


@patch("app.services.friendly_game_service.club_repository")

def test_rejects_incomplete_roster(
    mock_club_repository,
    valid_friendly_game_data,
):

    db = MagicMock()

    club = MagicMock()
    club.id = 1
    mock_club_repository.get_by_user_id.return_value = club

    valid_friendly_game_data.roster.players.pop()

    with pytest.raises(
        ValueError,
        match="A roster must have exactly 6 players",
    ):
        create_friendly_game(
            db=db,
            user_id=5,
            data=valid_friendly_game_data,
        )

    db.commit.assert_not_called()
    db.rollback.assert_called_once()
