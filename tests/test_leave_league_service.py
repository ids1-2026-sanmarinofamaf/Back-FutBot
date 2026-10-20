
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.models.league import LeagueState
from app.services.league_service import (
    leave_league,
    LeagueNotFound,
    LeagueCreatorCannotLeave,
    LeagueAlreadyStarted,
    LeagueParticipationNotFound,
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
    ):
        yield SimpleNamespace(
            league=league_repo,
            club=club_repo,
            participation=participation_repo,
            roster=roster_repo,
        )


@pytest.fixture
def valid_league(repos):
    # league created by club 1
    league = SimpleNamespace(
        id=10,
        creator_id=1,
        state=LeagueState.POR_COMENZAR,
    )

    # club 2 wants to leave the league
    club = SimpleNamespace(id=2)

    # roster associated with club 2
    roster = SimpleNamespace(
        id=30,
        club_id=2,
    )

    # club 2 participation in league 10
    participation = SimpleNamespace(
        league_id=10,
        club_id=2,
        roster_id=30,
        roster=roster,
    )

    # configure repository responses
    repos.league.get_by_id.return_value = league
    repos.club.get_by_user_id.return_value = club
    repos.participation.get_participation_by_club_and_league.return_value = participation

    # return test objects
    return SimpleNamespace(
        league=league,
        club=club,
        roster=roster,
        participation=participation,
    )


# successful leave
def test_leave_league_success(db, repos, valid_league):
    leave_league(
        db=db,
        league_id=10,
        user_id=5,
    )

    # verify repository lookups
    repos.league.get_by_id.assert_called_once_with(
        db=db,
        league_id=10,
    )

    repos.club.get_by_user_id.assert_called_once_with(
        db=db,
        user_id=5,
    )

    repos.participation.get_participation_by_club_and_league.assert_called_once_with(
        db=db,
        league_id=10,
        club_id=2,
    )

    # verify both deletions
    repos.participation.delete_participation.assert_called_once_with(
        db=db,
        participation=valid_league.participation,
    )

    repos.roster.delete_roster.assert_called_once_with(
        db=db,
        roster=valid_league.roster,
    )

    db.commit.assert_called_once()
    db.rollback.assert_not_called()


# league does not exist
def test_leave_league_not_found(db, repos):
    repos.league.get_by_id.return_value = None

    with pytest.raises(LeagueNotFound,match="League does not exist"):
        leave_league(
            db=db,
            league_id=999,
            user_id=5,
        )

    repos.participation.delete_participation.assert_not_called()
    repos.roster.delete_roster.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()


# user does not have a club
def test_leave_league_user_without_club(db, repos, valid_league):
    repos.club.get_by_user_id.return_value = None

    with pytest.raises(LeagueParticipationNotFound,match="User is not participating"):
        leave_league(db=db, league_id=10, user_id=5)

    repos.participation.delete_participation.assert_not_called()
    repos.roster.delete_roster.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()


# creator cannot leave
def test_creator_cannot_leave_league(db, repos, valid_league):
    valid_league.league.creator_id = valid_league.club.id

    with pytest.raises(LeagueCreatorCannotLeave,match="League creator cannot leave"):
        leave_league(db=db, league_id=10, user_id=5)

    repos.participation.delete_participation.assert_not_called()
    repos.roster.delete_roster.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()


# started or finished league
@pytest.mark.parametrize(
    "state",
    [
        LeagueState.INICIADA,
        LeagueState.FINALIZADA,
    ],
)
def test_cannot_leave_started_or_finished_league(db, repos, valid_league, state):
    valid_league.league.state = state

    with pytest.raises(LeagueAlreadyStarted,match="League has already started"):
        leave_league(db=db, league_id=10, user_id=5)

    repos.participation.delete_participation.assert_not_called()
    repos.roster.delete_roster.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()


# club does not participate
def test_participation_not_found(db, repos, valid_league):
    repos.participation.get_participation_by_club_and_league.return_value = None

    with pytest.raises(LeagueParticipationNotFound,match="User is not participating"):
        leave_league(db=db, league_id=10, user_id=5)

    repos.participation.delete_participation.assert_not_called()
    repos.roster.delete_roster.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()


# failure while deleting participation
def test_delete_participation_failure(db, repos, valid_league):
    repos.participation.delete_participation.side_effect = (RuntimeError("Database error"))

    with pytest.raises(RuntimeError, match="Database error"):
        leave_league(db=db, league_id=10, user_id=5)

    repos.roster.delete_roster.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()


# failure while deleting roster
def test_delete_roster_failure(db, repos, valid_league):
    repos.roster.delete_roster.side_effect = (RuntimeError("Roster deletion failed"))

    with pytest.raises(RuntimeError, match="Roster deletion failed"):
        leave_league(db=db, league_id=10, user_id=5)

    repos.participation.delete_participation.assert_called_once()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()


# failure during commit
def test_commit_failure(db, repos, valid_league):
    db.commit.side_effect = RuntimeError("Commit failed")

    with pytest.raises(RuntimeError, match="Commit failed"):
        leave_league(db=db, league_id=10, user_id=5)

    repos.participation.delete_participation.assert_called_once()
    repos.roster.delete_roster.assert_called_once()

    db.commit.assert_called_once()
    db.rollback.assert_called_once()
