from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.core.security import verify_password
from app.models.league import LeaguePrivacy
from app.schemas.league import LeagueCreate
from app.services.league_service import (
    create_league,
    ClubNotFound,
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
    ):
        # the user has club 7
        club_repo.get_by_user_id.return_value = SimpleNamespace(id=7)
        yield SimpleNamespace(
            league=league_repo,
            club=club_repo,
        )


def public_data():
    return LeagueCreate(
        name="Liga1",
        match_duration=10,
        max_clubs=8,
        privacy=LeaguePrivacy.PUBLICA,
        password="",
    )


# a public league is saved with the received values and no password
def test_create_public_league(db, repos):
    league = create_league(db, public_data(), 5)

    repos.club.get_by_user_id.assert_called_once_with(db, 5)
    repos.league.create.assert_called_once_with(db=db, league=league)

    assert league.name == "Liga1"
    assert league.match_duration == 10
    assert league.max_clubs == 8
    assert league.privacy == LeaguePrivacy.PUBLICA
    assert league.password_hash is None
    assert league.creator_id == 7

    db.commit.assert_called_once()
    db.rollback.assert_not_called()


# a private league is saved with the hashed password
def test_create_private_league_hashes_password(db, repos):
    data = LeagueCreate(
        name="Liga privada",
        match_duration=10,
        max_clubs=8,
        privacy=LeaguePrivacy.PRIVADA,
        password="clave123",
    )

    league = create_league(db, data, 5)

    assert league.privacy == LeaguePrivacy.PRIVADA
    assert league.password_hash != "clave123"
    assert verify_password("clave123", league.password_hash)
    db.commit.assert_called_once()


# a user without club cannot create a league
def test_create_league_without_club(db, repos):
    repos.club.get_by_user_id.return_value = None

    with pytest.raises(ClubNotFound):
        create_league(db, public_data(), 5)

    repos.league.create.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()


# if saving fails, the transaction is rolled back and the error propagates
def test_create_league_rollback_on_error(db, repos):
    repos.league.create.side_effect = RuntimeError("db error")

    with pytest.raises(RuntimeError):
        create_league(db, public_data(), 5)

    db.commit.assert_not_called()
    db.rollback.assert_called_once()
