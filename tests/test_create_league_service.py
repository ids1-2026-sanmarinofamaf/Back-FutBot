from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.core.security import verify_password
from app.models.league import LeaguePrivacy
from app.models.roster import Formation
from app.schemas.league import LeagueCreate
from app.services.league_service import (
    create_league,
    ClubNotFound,
)


CLUB_ID = 7


@pytest.fixture
def db():
    return MagicMock()


@pytest.fixture
# mock repositories used by the service
def repos():
    with (
        patch("app.services.league_service.league_repository") as league_repo,
        patch("app.services.league_service.club_repository") as club_repo,
        patch("app.services.league_service.roster_repository") as roster_repo,
        patch("app.services.league_service.player_repository") as player_repo,
        patch("app.services.league_service.behavior_repository") as behavior_repo,
        patch("app.services.league_service.league_participation_repository") as participation_repo,
    ):
        # the user has club 7, and every player and behavior belongs to it
        club_repo.get_by_user_id.return_value = SimpleNamespace(id=CLUB_ID)
        player_repo.get_by_id.return_value = SimpleNamespace(club_id=CLUB_ID)
        behavior_repo.get_by_id.return_value = SimpleNamespace(club_id=CLUB_ID, is_default=False)

        # simulate the ids the database assigns on flush
        def save_roster(db, roster):
            roster.id = 30

        def create_league_row(db, league):
            league.id = 10
            return league

        roster_repo.save.side_effect = save_roster
        league_repo.create.side_effect = create_league_row

        yield SimpleNamespace(
            league=league_repo,
            club=club_repo,
            roster=roster_repo,
            player=player_repo,
            behavior=behavior_repo,
            participation=participation_repo,
        )


def roster_data():
    slots = ["left", "center", "right"]

    return {
        "formation": "offensive",
        "players": [
            {
                "player_id": i + 1,
                "is_starter": i < 3,
                "slot": slots[i] if i < 3 else None,
                "initial_behavior_id": 1 if i < 3 else None,
            }
            for i in range(6)
        ],
    }


def league_data(**overrides):
    data = {
        "nombre": "Liga1",
        "duracion_partido": 10,
        "max_usuarios": 8,
        "es_privada": False,
        "password": "",
        "roster": roster_data(),
    }
    data.update(overrides)
    return LeagueCreate.model_validate(data)


# a public league is saved with the received values and no password
def test_create_public_league(db, repos):
    league = create_league(db, league_data(), 5)

    repos.club.get_by_user_id.assert_called_once_with(db, 5)
    repos.league.create.assert_called_once_with(db=db, league=league)

    assert league.name == "Liga1"
    assert league.match_duration == 10
    assert league.max_clubs == 8
    assert league.privacy == LeaguePrivacy.PUBLICA
    assert league.password_hash is None
    assert league.creator_id == CLUB_ID

    db.commit.assert_called_once()
    db.rollback.assert_not_called()


# a private league is saved with the hashed password
def test_create_private_league_hashes_password(db, repos):
    league = create_league(db, league_data(es_privada=True, password="clave123"), 5)

    assert league.privacy == LeaguePrivacy.PRIVADA
    assert league.password_hash != "clave123"
    assert verify_password("clave123", league.password_hash)
    db.commit.assert_called_once()


# the roster is built from the body and saved for the creator's club
def test_create_league_saves_roster(db, repos):
    create_league(db, league_data(), 5)

    repos.roster.save.assert_called_once()
    roster = repos.roster.save.call_args.args[1]

    assert roster.club_id == CLUB_ID
    assert roster.formation == Formation.OFFENSIVE
    assert [p.player_id for p in roster.players] == [1, 2, 3, 4, 5, 6]
    assert sum(p.is_starter for p in roster.players) == 3


# the creator is registered as participant with the saved roster
def test_create_league_creates_creator_participation(db, repos):
    create_league(db, league_data(), 5)

    repos.participation.create_participation.assert_called_once_with(
        db=db,
        league_id=10,
        club_id=CLUB_ID,
        roster_id=30,
    )


# a user without club cannot create a league
def test_create_league_without_club(db, repos):
    repos.club.get_by_user_id.return_value = None

    with pytest.raises(ClubNotFound):
        create_league(db, league_data(), 5)

    repos.league.create.assert_not_called()
    repos.participation.create_participation.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()


# an invalid roster is rejected before saving anything
def test_create_league_invalid_roster(db, repos):
    data = league_data()
    data.roster.players.pop()

    with pytest.raises(ValueError, match="exactly 6 players"):
        create_league(db, data, 5)

    repos.roster.save.assert_not_called()
    repos.league.create.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()


# a player of another club is rejected
def test_create_league_player_of_other_club(db, repos):
    repos.player.get_by_id.return_value = SimpleNamespace(club_id=99)

    with pytest.raises(ValueError, match="does not belong"):
        create_league(db, league_data(), 5)

    repos.roster.save.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()


# if creating the participation fails, everything is rolled back
def test_create_league_rollback_when_participation_fails(db, repos):
    repos.participation.create_participation.side_effect = RuntimeError("db error")

    with pytest.raises(RuntimeError):
        create_league(db, league_data(), 5)

    db.commit.assert_not_called()
    db.rollback.assert_called_once()


# if saving the league fails, the transaction is rolled back and the error propagates
def test_create_league_rollback_on_error(db, repos):
    repos.league.create.side_effect = RuntimeError("db error")

    with pytest.raises(RuntimeError):
        create_league(db, league_data(), 5)

    repos.participation.create_participation.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()
