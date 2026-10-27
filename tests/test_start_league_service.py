
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.models.league import LeagueState
from app.services.league_service import (
    start_league,
    LeagueNotFound,
    LeagueForbidden,
    LeagueAlreadyStarted,
    InvalidLeagueState,
    InsufficientLeagueParticipants,
)


@pytest.fixture
def db():
    return MagicMock()


@pytest.fixture
def repos():
    with (
        patch("app.services.league_service.league_repository") as league_repo,
        patch("app.services.league_service.club_repository") as club_repo,
        patch("app.services.league_service.league_participation_repository") as participation_repo,
    ):
        yield SimpleNamespace(
            league=league_repo,
            club=club_repo,
            participation=participation_repo,
        )


@pytest.fixture
def valid_league(repos):
    league = SimpleNamespace(
        id=10,
        creator_id=1,
        state=LeagueState.POR_COMENZAR,
    )

    club = SimpleNamespace(id=1)

    repos.league.get_by_id.return_value = league
    repos.club.get_by_user_id.return_value = club
    repos.participation.count_participations.return_value = 3

    return league


# successful start
def test_start_league_success(db, repos, valid_league):
    start_league(
        db=db,
        league_id=10,
        user_id=5,
        requested_state=LeagueState.INICIADA,
    )

    repos.league.update_state.assert_called_once_with(
        db=db,
        league=valid_league,
        state=LeagueState.INICIADA,
    )

    repos.participation.count_participations.assert_called_once_with(
        db=db,
        league_id=10,
    )

    db.commit.assert_called_once()
    db.rollback.assert_not_called()


# league does not exist
def test_start_league_not_found(db, repos):
    repos.league.get_by_id.return_value = None

    with pytest.raises(LeagueNotFound):
        start_league(db, 999, 5, LeagueState.INICIADA)

    repos.league.update_state.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()


# user is not the creator
def test_start_league_not_creator(db, repos, valid_league):
    repos.club.get_by_user_id.return_value = SimpleNamespace(id=2)

    with pytest.raises(LeagueForbidden):
        start_league(db, 10, 5, LeagueState.INICIADA)

    repos.league.update_state.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()


# user has no club
def test_start_league_without_club(db, repos, valid_league):
    repos.club.get_by_user_id.return_value = None

    with pytest.raises(LeagueForbidden):
        start_league(db, 10, 5, LeagueState.INICIADA)

    db.commit.assert_not_called()
    db.rollback.assert_called_once()


# invalid requested state
@pytest.mark.parametrize(
    "state",
    [
        LeagueState.POR_COMENZAR,
        LeagueState.FINALIZADA,
    ],
)
def test_invalid_requested_state(db, repos, valid_league, state):
    with pytest.raises(InvalidLeagueState):
        start_league(db, 10, 5, state)

    repos.league.update_state.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()


# slready started or finished
@pytest.mark.parametrize(
    "state",
    [
        LeagueState.INICIADA,
        LeagueState.FINALIZADA,
    ],
)
def test_start_league_already_started(
    db, repos, valid_league, state
):
    valid_league.state = state

    with pytest.raises(LeagueAlreadyStarted):
        start_league(db, 10, 5, LeagueState.INICIADA)

    repos.league.update_state.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()


# insufficient participants
def test_insufficient_participants(db, repos, valid_league):
    repos.participation.count_participations.return_value = 2

    with pytest.raises(InsufficientLeagueParticipants):
        start_league(db, 10, 5, LeagueState.INICIADA)

    repos.league.update_state.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()


# repository fails while updating state
def test_update_state_failure(db, repos, valid_league):
    repos.league.update_state.side_effect = RuntimeError(
        "Database error"
    )

    with pytest.raises(RuntimeError, match="Database error"):
        start_league(db, 10, 5, LeagueState.INICIADA)

    db.commit.assert_not_called()
    db.rollback.assert_called_once()


# database commit fails
def test_commit_failure(db, repos, valid_league):
    db.commit.side_effect = RuntimeError("Commit failed")

    with pytest.raises(RuntimeError, match="Commit failed"):
        start_league(db, 10, 5, LeagueState.INICIADA)

    db.commit.assert_called_once()
    db.rollback.assert_called_once()
