import pytest

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from sqlalchemy.exc import IntegrityError

from app.schemas.friendly_game import FriendlyGameJoin
from app.schemas.roster import RosterCreate, PlayerOnRosterCreate

from app.services.friendly_game_service import (
    join_friendly_game,
    FriendlyGameNotFound,
    FriendlyGameNotAvailable,
    FriendlyGameFull,
    AlreadyParticipating,
    InvalidRoster,
)

from app.models.roster import Formation
from app.models.player_on_roster import RosterSlot
from app.models.friendly_game import FriendlyGameState
from app.models.friendly_game_participation import FriendlyGameRole


@pytest.fixture
def valid_join_data():
    return FriendlyGameJoin(
        roster=RosterCreate(
            formation=Formation.OFFENSIVE,
            players=[
                PlayerOnRosterCreate(
                    player_id=1,
                    is_starter=True,
                    slot=RosterSlot.LEFT,
                    initial_behavior_id=10,
                ),
                PlayerOnRosterCreate(
                    player_id=2,
                    is_starter=True,
                    slot=RosterSlot.CENTER,
                    initial_behavior_id=11,
                ),
                PlayerOnRosterCreate(
                    player_id=3,
                    is_starter=True,
                    slot=RosterSlot.RIGHT,
                    initial_behavior_id=12,
                ),
                PlayerOnRosterCreate(
                    player_id=4,
                    is_starter=False,
                    slot=None,
                    initial_behavior_id=None,
                ),
                PlayerOnRosterCreate(
                    player_id=5,
                    is_starter=False,
                    slot=None,
                    initial_behavior_id=None,
                ),
                PlayerOnRosterCreate(
                    player_id=6,
                    is_starter=False,
                    slot=None,
                    initial_behavior_id=None,
                ),
            ],
        )
    )


@pytest.fixture
def repos():
    with (
        patch("app.services.friendly_game_service.club_repository") as club_repository,
        patch("app.services.friendly_game_service.player_repository") as player_repository,
        patch("app.services.friendly_game_service.behavior_repository") as behavior_repository,
        patch("app.services.friendly_game_service.roster_repository") as roster_repository,
        patch("app.services.friendly_game_service.friendly_game_repository") as friendly_game_repository,
    ):
        yield SimpleNamespace(
            club=club_repository,
            player=player_repository,
            behavior=behavior_repository,
            roster=roster_repository,
            friendly_game=friendly_game_repository,
        )


def configure_joinable_game(repos):
    club = MagicMock()
    club.id = 2
    repos.club.get_by_user_id.return_value = club

    friendly_game = MagicMock()
    friendly_game.id = 30
    friendly_game.state = FriendlyGameState.POR_COMENZAR
    repos.friendly_game.get_by_id.return_value = friendly_game

    repos.friendly_game.get_participation_by_club.return_value = None
    repos.friendly_game.count_participations.return_value = 1

    return club, friendly_game

def test_join_success(
    repos,
    valid_join_data,
):
    db = MagicMock()

    club, friendly_game = configure_joinable_game(repos)

    player = MagicMock()
    player.club_id = club.id
    repos.player.get_by_id.return_value = player

    behavior = MagicMock()
    behavior.club_id = club.id
    repos.behavior.get_by_id.return_value = behavior

    def save_roster(db, roster):
        roster.id = 20

    repos.roster.save.side_effect = save_roster

    participation = MagicMock()
    participation.id = 40
    repos.friendly_game.create_participation.return_value = participation

    result_participation, result_roster = join_friendly_game(
        db=db,
        friendly_game_id=friendly_game.id,
        user_id=5,
        data=valid_join_data,
    )

    assert result_participation.id == 40
    assert result_roster.id == 20

    repos.friendly_game.create_participation.assert_called_once_with(
        db=db,
        friendly_game_id=30,
        club_id=2,
        roster_id=20,
        role=FriendlyGameRole.GUEST,
    )

    db.commit.assert_called_once()
    db.rollback.assert_not_called()


def test_join_friendly_game_not_found(
    repos,
    valid_join_data,
):
    db = MagicMock()

    repos.club.get_by_user_id.return_value = MagicMock(id=2)
    repos.friendly_game.get_by_id.return_value = None

    with pytest.raises(
        FriendlyGameNotFound,
        match="Friendly game does not exist",
    ):
        join_friendly_game(
            db=db,
            friendly_game_id=999,
            user_id=5,
            data=valid_join_data,
        )

    db.commit.assert_not_called()
    db.rollback.assert_called_once()


@pytest.mark.parametrize(
    "state",
    [
        FriendlyGameState.JUGANDO,
        FriendlyGameState.FINALIZADO,
    ],
)
def test_join_rejects_unavailable_state(
    repos,
    valid_join_data,
    state,
):
    db = MagicMock()

    repos.club.get_by_user_id.return_value = MagicMock(id=2)

    friendly_game = MagicMock()
    friendly_game.id = 30
    friendly_game.state = state

    repos.friendly_game.get_by_id.return_value = friendly_game

    with pytest.raises(
        FriendlyGameNotAvailable,
        match="Friendly game is not available",
    ):
        join_friendly_game(
            db=db,
            friendly_game_id=30,
            user_id=5,
            data=valid_join_data,
        )

    db.commit.assert_not_called()
    db.rollback.assert_called_once()

def test_join_rejects_already_participating(
    repos,
    valid_join_data,
):
    db = MagicMock()

    configure_joinable_game(repos)

    repos.friendly_game.get_participation_by_club.return_value = (
        MagicMock()
    )

    with pytest.raises(
        AlreadyParticipating,
        match="already participating",
    ):
        join_friendly_game(
            db=db,
            friendly_game_id=30,
            user_id=5,
            data=valid_join_data,
        )

    db.commit.assert_not_called()
    db.rollback.assert_called_once()

def test_join_rejects_full_game(
    repos,
    valid_join_data,
):
    db = MagicMock()

    configure_joinable_game(repos)

    repos.friendly_game.count_participations.return_value = 2

    with pytest.raises(
        FriendlyGameFull,
        match="Friendly game is full",
    ):
        join_friendly_game(
            db=db,
            friendly_game_id=30,
            user_id=5,
            data=valid_join_data,
        )

    db.commit.assert_not_called()
    db.rollback.assert_called_once()

def test_join_rejects_invalid_roster(
    repos,
    valid_join_data,
):
    db = MagicMock()

    configure_joinable_game(repos)

    valid_join_data.roster.players.pop()

    with pytest.raises(
        InvalidRoster,
        match="A roster must have exactly 6 players",
    ):
        join_friendly_game(
            db=db,
            friendly_game_id=30,
            user_id=5,
            data=valid_join_data,
        )

    db.commit.assert_not_called()
    db.rollback.assert_called_once()


def test_join_rejects_player_from_another_club(
    repos,
    valid_join_data,
):
    db = MagicMock()

    configure_joinable_game(repos)

    player = MagicMock()
    player.club_id = 99
    repos.player.get_by_id.return_value = player

    with pytest.raises(
        InvalidRoster,
        match="Player does not belong to user's club",
    ):
        join_friendly_game(
            db=db,
            friendly_game_id=30,
            user_id=5,
            data=valid_join_data,
        )

    db.commit.assert_not_called()
    db.rollback.assert_called_once()

def test_join_rejects_behavior_from_another_club(
    repos,
    valid_join_data,
):
    db = MagicMock()

    club, _ = configure_joinable_game(repos)

    player = MagicMock()
    player.club_id = club.id
    repos.player.get_by_id.return_value = player

    behavior = MagicMock()
    behavior.club_id = 99
    repos.behavior.get_by_id.return_value = behavior

    with pytest.raises(
        InvalidRoster,
        match="Behavior does not belong to user's club",
    ):
        join_friendly_game(
            db=db,
            friendly_game_id=30,
            user_id=5,
            data=valid_join_data,
        )

    db.commit.assert_not_called()
    db.rollback.assert_called_once()