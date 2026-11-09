import pytest
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.database import engine
from app.models.user import User
from app.models.club import Club
from app.models.roster import Roster, Formation
from app.models.league import League, LeagueState, LeaguePrivacy
from app.models.league_participation import LeagueParticipation
from app.repositories import league_repository
from app.services.league_service import (
    cancel_league,
    LeagueNotFound,
    LeagueForbidden,
    LeagueAlreadyStarted,
)


LEAGUE_NAME = "Cancel League Test"


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


def create_club(db, index: int) -> Club:
    user = User(
        email=f"cancel_league_test_{index}@example.com",
        hash_passwd="test_hash",
    )
    db.add(user)
    db.flush()

    club = Club(user_id=user.id, name=f"Cancel Club {index}")
    db.add(club)
    db.flush()

    return club


@pytest.fixture
def setup(db):
    clubs = [create_club(db, i) for i in range(3)]

    league = League(
        name=LEAGUE_NAME,
        match_duration=10,
        max_clubs=8,
        state=LeagueState.POR_COMENZAR,
        privacy=LeaguePrivacy.PUBLICA,
        password_hash=None,
        creator_id=clubs[0].id,
    )
    db.add(league)
    db.flush()

    # a roster of each club that does not belong to the league and must survive
    other_rosters = []
    league_rosters = []

    for club in clubs:
        other_roster = Roster(club_id=club.id, formation=Formation.OFFENSIVE)
        league_roster = Roster(club_id=club.id, formation=Formation.DEFENSIVE)
        db.add_all([other_roster, league_roster])
        db.flush()

        db.add(
            LeagueParticipation(
                league_id=league.id,
                club_id=club.id,
                roster_id=league_roster.id,
            )
        )
        other_rosters.append(other_roster.id)
        league_rosters.append(league_roster.id)

    db.commit()

    return {
        "league_id": league.id,
        "clubs": clubs,
        "other_rosters": other_rosters,
        "league_rosters": league_rosters,
    }


def count_participations(db, league_id: int) -> int:
    return db.scalar(
        select(func.count())
        .select_from(LeagueParticipation)
        .where(LeagueParticipation.league_id == league_id)
    )


def count_rosters(db, roster_ids: list[int]) -> int:
    return db.scalar(
        select(func.count())
        .select_from(Roster)
        .where(Roster.id.in_(roster_ids))
    )


def test_cancel_removes_league_participations_and_league_rosters(db, setup):
    host = setup["clubs"][0]

    cancel_league(db=db, league_id=setup["league_id"], user_id=host.user_id)

    assert db.get(League, setup["league_id"]) is None
    assert count_participations(db, setup["league_id"]) == 0
    assert count_rosters(db, setup["league_rosters"]) == 0


def test_cancel_keeps_other_rosters_of_the_participants(db, setup):
    host = setup["clubs"][0]

    cancel_league(db=db, league_id=setup["league_id"], user_id=host.user_id)

    assert count_rosters(db, setup["other_rosters"]) == len(setup["other_rosters"])


def test_cancelled_league_is_not_listed(db, setup):
    host = setup["clubs"][0]

    cancel_league(db=db, league_id=setup["league_id"], user_id=host.user_id)

    visible_ids = [league.id for league in league_repository.get_visible_leagues(db)]
    assert setup["league_id"] not in visible_ids


def test_non_host_participant_cannot_cancel(db, setup):
    participant = setup["clubs"][1]

    with pytest.raises(LeagueForbidden):
        cancel_league(db=db, league_id=setup["league_id"], user_id=participant.user_id)

    assert db.get(League, setup["league_id"]) is not None
    assert count_participations(db, setup["league_id"]) == 3
    assert count_rosters(db, setup["league_rosters"]) == 3


@pytest.mark.parametrize("state", [LeagueState.INICIADA, LeagueState.FINALIZADA])
def test_started_or_finished_league_cannot_be_cancelled(db, setup, state):
    host = setup["clubs"][0]
    league = db.get(League, setup["league_id"])
    league.state = state
    db.commit()

    with pytest.raises(LeagueAlreadyStarted):
        cancel_league(db=db, league_id=setup["league_id"], user_id=host.user_id)

    league = db.get(League, setup["league_id"])
    assert league is not None
    assert league.state == state
    assert count_participations(db, setup["league_id"]) == 3


def test_nonexistent_league_cannot_be_cancelled(db, setup):
    host = setup["clubs"][0]

    with pytest.raises(LeagueNotFound):
        cancel_league(db=db, league_id=999_999, user_id=host.user_id)


def test_second_cancellation_is_rejected(db, setup):
    host = setup["clubs"][0]

    cancel_league(db=db, league_id=setup["league_id"], user_id=host.user_id)

    with pytest.raises(LeagueNotFound):
        cancel_league(db=db, league_id=setup["league_id"], user_id=host.user_id)
