from sqlalchemy.orm import Session
from app.database import engine
from sqlalchemy import select, func

import pytest

from app.models.user import User
from app.models.club import Club
from app.models.player import Player
from app.models.league import League, LeagueState, LeaguePrivacy
from app.repositories import behavior_repository
from app.schemas.league import LeagueJoin
from app.schemas.roster import RosterCreate, PlayerOnRosterCreate
from app.models.player_on_roster import RosterSlot
from app.models.roster import Formation
from app.services.league_service import (
    join_league,
    AlreadyParticipating,
    InvalidRoster,
    InvalidLeaguePassword,
)
from app.models.league_participation import LeagueParticipation
from app.models.roster import Roster
from app.core.security import get_password_hash



@pytest.fixture
def db():
    with engine.connect() as connection:
        connection.exec_driver_sql("BEGIN")

        transaction = connection.get_transaction()

        with Session(
            bind=connection,
            join_transaction_mode="create_savepoint",
        ) as session:
            yield session

        transaction.rollback()

        with Session(engine) as check_db:
            user = check_db.scalar(
                select(User).where(
                    User.email == "join_league_test@example.com"
                )
            )

            assert user is None, "El usuario sigue en la base de datos"

@pytest.fixture
def test_user(db):
    user = User(
        email="join_league_test@example.com",
        hash_passwd="test_hash",
    )

    db.add(user)
    db.flush()

    return user


@pytest.fixture
def test_club(db, test_user):
    club = Club(
        user_id=test_user.id,
        name="test_club",
    )

    db.add(club)
    db.flush()

    return club


@pytest.fixture
def test_players(db, test_club):
    players = []

    for i in range(6):
        player = Player(
            club_id=test_club.id,
            name=f"Player {i + 1}",
            power=60,
            agility=60,
            control=60,
            speed=60,
            strength=60,
        )

        players.append(player)

    db.add_all(players)
    db.flush()

    return players


@pytest.fixture
def test_league_creator(db):
    user = User(
        email="league_creator_test@example.com",
        hash_passwd="test_hash",
    )

    db.add(user)
    db.flush()

    club = Club(
        user_id=user.id,
        name="Creator Club",
    )

    db.add(club)
    db.flush()

    return club


@pytest.fixture
def test_league(db, test_league_creator):
    league = League(
        name="Test League",
        match_duration=10,
        max_clubs=8,
        state=LeagueState.POR_COMENZAR,
        privacy=LeaguePrivacy.PUBLICA,
        password_hash=None,
        creator_id=test_league_creator.id,
    )

    db.add(league)
    db.flush()

    return league


@pytest.fixture
def test_behavior(db, test_club):
    behavior = behavior_repository.get_available_by_name(
        db=db,
        club_id=test_club.id,
        name="Attacker",
    )

    assert behavior is not None
    assert behavior.is_default is True

    return behavior


@pytest.fixture
def valid_join_data(test_players, test_behavior):
    players = []

    for i, player in enumerate(test_players):
        is_starter = i < 3

        players.append(
            PlayerOnRosterCreate(
                player_id=player.id,
                is_starter=is_starter,
                slot=(
                    [RosterSlot.LEFT, RosterSlot.CENTER, RosterSlot.RIGHT][i]
                    if is_starter
                    else None
                ),
                initial_behavior_id=(
                    test_behavior.id if is_starter else None
                ),
            )
        )

    roster = RosterCreate(
        formation=Formation.DEFENSIVE,
        players=players,
    )

    return LeagueJoin(
        roster=roster,
        password=None
    )


def test_join_league_persists_participation(
    db,
    test_user,
    test_club,
    test_league,
    valid_join_data,
):
    participation, roster = join_league(
        db=db,
        league_id=test_league.id,
        user_id=test_user.id,
        data=valid_join_data,
    )

    db.expire_all()

    saved_participation = db.get(
        LeagueParticipation,
        (test_league.id, test_club.id),
    )

    assert saved_participation is not None
    assert saved_participation.league_id == test_league.id
    assert saved_participation.club_id == test_club.id

    saved_roster = db.get(
        Roster,
        saved_participation.roster_id,
    )

    assert saved_roster is not None
    assert saved_roster.club_id == test_club.id
    assert saved_roster.formation == valid_join_data.roster.formation
    assert len(saved_roster.players) == 6

    assert saved_participation.roster_id == saved_roster.id

    expected_player_ids = {
        player.player_id
        for player in valid_join_data.roster.players
    }

    saved_player_ids = {
        player.player_id
        for player in saved_roster.players
    }

    assert saved_player_ids == expected_player_ids


def test_join_league_already_participating(
    db,
    test_user,
    test_club,
    test_league,
    valid_join_data,
):
    join_league(
        db=db,
        league_id=test_league.id,
        user_id=test_user.id,
        data=valid_join_data,
    )

    with pytest.raises(AlreadyParticipating):
        join_league(
            db=db,
            league_id=test_league.id,
            user_id=test_user.id,
            data=valid_join_data,
        )

    participation_count = db.scalar(
        select(func.count())
        .select_from(LeagueParticipation)
        .where(LeagueParticipation.league_id == test_league.id)
    )

    assert participation_count == 1

    roster_count = db.scalar(
        select(func.count())
        .select_from(Roster)
        .where(Roster.club_id == test_club.id)
    )

    assert roster_count == 1


@pytest.fixture
def foreign_player(db, test_league_creator):
    player = Player(
        club_id=test_league_creator.id,
        name="Foreign Player",
        power=60,
        agility=60,
        control=60,
        speed=60,
        strength=60,
    )

    db.add(player)
    db.flush()

    return player


def test_join_league_rejects_foreign_player(
    db,
    test_user,
    test_club,
    test_league,
    valid_join_data,
    foreign_player,
):
    valid_join_data.roster.players[0].player_id = foreign_player.id

    with pytest.raises(InvalidRoster):
        join_league(
            db=db,
            league_id=test_league.id,
            user_id=test_user.id,
            data=valid_join_data,
        )

    participation_count = db.scalar(
        select(func.count())
        .select_from(LeagueParticipation)
        .where(LeagueParticipation.league_id == test_league.id)
    )

    assert participation_count == 0

    roster_count = db.scalar(
        select(func.count())
        .select_from(Roster)
        .where(Roster.club_id == test_club.id)
    )

    assert roster_count == 0


@pytest.fixture
def test_private_league(db, test_league):
    test_league.privacy = LeaguePrivacy.PRIVADA
    test_league.password_hash = get_password_hash("secret123")

    db.flush()

    return test_league


def test_join_private_league_without_password(
    db,
    test_user,
    test_club,
    test_private_league,
    valid_join_data,
):
    valid_join_data.password = None

    with pytest.raises(InvalidLeaguePassword):
        join_league(
            db=db,
            league_id=test_private_league.id,
            user_id=test_user.id,
            data=valid_join_data,
        )

    participation_count = db.scalar(
        select(func.count())
        .select_from(LeagueParticipation)
        .where(LeagueParticipation.league_id == test_private_league.id)
    )

    assert participation_count == 0

    roster_count = db.scalar(
        select(func.count())
        .select_from(Roster)
        .where(Roster.club_id == test_club.id)
    )

    assert roster_count == 0


def test_join_private_league_with_wrong_password(
    db,
    test_user,
    test_club,
    test_private_league,
    valid_join_data,
):
    valid_join_data.password = "wrong_password"

    with pytest.raises(InvalidLeaguePassword):
        join_league(
            db=db,
            league_id=test_private_league.id,
            user_id=test_user.id,
            data=valid_join_data,
        )

    participation_count = db.scalar(
        select(func.count())
        .select_from(LeagueParticipation)
        .where(LeagueParticipation.league_id == test_private_league.id)
    )

    assert participation_count == 0

    roster_count = db.scalar(
        select(func.count())
        .select_from(Roster)
        .where(Roster.club_id == test_club.id)
    )

    assert roster_count == 0


def test_join_private_league_with_correct_password(
    db,
    test_user,
    test_club,
    test_private_league,
    valid_join_data,
):
    valid_join_data.password = "secret123"

    join_league(
            db=db,
            league_id=test_private_league.id,
            user_id=test_user.id,
            data=valid_join_data,
        )

    participation_count = db.scalar(
        select(func.count())
        .select_from(LeagueParticipation)
        .where(LeagueParticipation.league_id == test_private_league.id)
    )

    assert participation_count == 1

    roster_count = db.scalar(
        select(func.count())
        .select_from(Roster)
        .where(Roster.club_id == test_club.id)
    )

    assert roster_count == 1