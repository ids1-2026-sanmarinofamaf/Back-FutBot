import pytest

from types import SimpleNamespace
from unittest.mock import MagicMock, patch


from app.schemas.roster import RosterCreate, PlayerOnRosterCreate
from app.schemas.league import LeagueJoin
from app.models.league import LeagueState, LeaguePrivacy
from app.services.league_service import (
    join_league,
    LeagueNotFound,
    LeagueNotAvailable,
    AlreadyParticipating,
    LeagueFull,
)


@pytest.fixture
def db():
    return MagicMock()


@pytest.fixture
# mock repositories used by the service
def repos():
    with (
        patch("app.services.league_service.league_repository") as league_repo,
        patch("app.services.league_service.club_repository") as club_repo,
        patch("app.services.league_service.league_participation_repository") as participation_repo,
        patch("app.services.league_service.roster_repository") as roster_repo,
        patch("app.services.league_service.behavior_repository") as behavior_repo,
        patch("app.services.league_service.player_repository") as player_repo,
    ):
        yield SimpleNamespace(
            league=league_repo,
            club=club_repo,
            participation=participation_repo,
            roster=roster_repo,
            behavior=behavior_repo,
            player=player_repo,
        )


@pytest.fixture
def valid_data(valid_roster):
    roster_data = RosterCreate(
        formation=valid_roster.formation,
        players=[
            PlayerOnRosterCreate(
                player_id=player.player_id,
                is_starter=player.is_starter,
                slot=player.slot,
                initial_behavior_id=player.initial_behavior_id,
            )
            for player in valid_roster.players
        ],
    )

    return LeagueJoin(
        roster=roster_data,
        password=None,
    )


def mock_get_player(db, player_id):
    return SimpleNamespace(
        id=player_id,
        club_id=2,
    )


def mock_save_roster(db, roster):
    roster.id = 30


@pytest.fixture
def valid_join_repos(repos):

    repos.league.get_by_id.return_value = SimpleNamespace(
        id=10,
        creator_id=1,
        state=LeagueState.POR_COMENZAR,
        privacy=LeaguePrivacy.PUBLICA,
        max_clubs=8,
    )

    repos.club.get_by_user_id.return_value = SimpleNamespace(id=2)

    repos.participation.get_participation_by_club_and_league.return_value = None

    repos.league.count_participations.return_value = 7

    repos.player.get_by_id.side_effect = mock_get_player

    repos.behavior.get_by_id.return_value = SimpleNamespace(
        id=1,
        is_default=False,
        club_id=2,
    )

    repos.roster.save.side_effect = mock_save_roster

    repos.participation.create_participation.return_value = SimpleNamespace(
        league_id=10,
        club_id=2,
        roster_id=30,
    )

    return repos


def test_join_league_not_found(db, repos, valid_data):
    repos.league.get_by_id.return_value = None

    with pytest.raises(LeagueNotFound, match="League does not exist"):
        join_league(
            db=db,
            league_id=999,
            user_id=5,
            data=valid_data,
        )

    db.commit.assert_not_called()
    db.rollback.assert_called_once()

    repos.roster.save.assert_not_called()
    repos.participation.create_participation.assert_not_called()


@pytest.mark.parametrize(
    "state",
    [
        LeagueState.INICIADA,
        LeagueState.FINALIZADA,
    ],
)
def test_join_league_not_available(db, repos, valid_data, state):
    repos.league.get_by_id.return_value = SimpleNamespace(
        id=10,
        creator_id=1,
        state=state,
        privacy=LeaguePrivacy.PUBLICA,
    )

    with pytest.raises(LeagueNotAvailable, match="League is not available"):
        join_league(
            db=db,
            league_id=10,
            user_id=2,
            data=valid_data,
        )

    db.commit.assert_not_called()
    db.rollback.assert_called_once()

    repos.roster.save.assert_not_called()
    repos.participation.create_participation.assert_not_called()


def test_join_league_already_participating(
    db,
    valid_join_repos,
    valid_data,
):
    valid_join_repos.participation.get_participation_by_club_and_league.return_value = SimpleNamespace(
        league_id=10,
        club_id=2,
    )

    with pytest.raises(
        AlreadyParticipating,
        match="Club is already participating in this league",
    ):
        join_league(
            db=db,
            league_id=10,
            user_id=5,
            data=valid_data,
        )

    db.commit.assert_not_called()
    db.rollback.assert_called_once()

    valid_join_repos.roster.save.assert_not_called()
    valid_join_repos.participation.create_participation.assert_not_called()
    valid_join_repos.participation.get_participation_by_club_and_league.assert_called_once_with(
        db=db,
        league_id=10,
        club_id=2,
    )

def test_join_league_full(db, valid_join_repos, valid_data):
    valid_join_repos.league.count_participations.return_value = 8

    with pytest.raises(LeagueFull, match="League is full"):
        join_league(
            db=db,
            league_id=10,
            user_id=5,
            data=valid_data,
        )

    db.commit.assert_not_called()
    db.rollback.assert_called_once()

    valid_join_repos.roster.save.assert_not_called()
    valid_join_repos.participation.create_participation.assert_not_called()
    valid_join_repos.participation.get_participation_by_club_and_league.assert_called_once_with(
        db=db,
        league_id=10,
        club_id=2,
    )
    valid_join_repos.league.count_participations.assert_called_once_with(
        db=db,
        league_id=10,
    )


def test_join_league_success(db, valid_join_repos, valid_data):

    participation, roster = join_league(
        db=db,
        league_id=10,
        user_id=5,
        data=valid_data,
    )

    assert participation.league_id == 10
    assert participation.club_id == 2

    assert roster.id == 30
    assert roster.club_id == 2
    assert len(roster.players) == 6

    assert roster.formation == valid_data.roster.formation
    assert participation.roster_id == roster.id

    db.commit.assert_called_once()
    db.rollback.assert_not_called()

    valid_join_repos.roster.save.assert_called_once()
    valid_join_repos.participation.create_participation.assert_called_once_with(
        db=db,
        league_id=10,
        club_id=2,
        roster_id=30,
    )


def test_join_league_with_default_behaviors(
    db,
    valid_join_repos,
    valid_data,
):
    valid_join_repos.behavior.get_by_id.return_value = SimpleNamespace(
        id=1,
        is_default=True,
        club_id=None,
    )

    participation, roster = join_league(
        db=db,
        league_id=10,
        user_id=5,
        data=valid_data,
    )

    assert participation.club_id == 2

    starters = [p for p in roster.players if p.is_starter]
    substitutes = [p for p in roster.players if not p.is_starter]

    assert len(starters) == 3
    assert len(substitutes) == 3

    assert all(p.initial_behavior_id == 1 for p in starters)
    assert all(p.initial_behavior_id is None for p in substitutes)

    assert valid_join_repos.behavior.get_by_id.call_count == 3

    db.commit.assert_called_once()
    db.rollback.assert_not_called()