import pytest

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import engine
from app.models.user import User
from app.models.club import Club
from app.models.league import League, LeagueState, LeaguePrivacy
from app.models.league_participation import LeagueParticipation
from app.models.roster import Roster, Formation
from app.repositories.league_repository import get_visible_leagues


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


@pytest.fixture
def clubs(db):
    clubs = []

    for i in range(3):
        user = User(
            email=f"league_repository_user_{i}@example.com",
            hash_passwd="test_hash",
        )
        db.add(user)
        db.flush()

        club = Club(
            user_id=user.id,
            name=f"League Repository Club {i}",
        )
        db.add(club)
        db.flush()

        clubs.append(club)

    return clubs


def create_league(
    db,
    creator,
    name,
    state=LeagueState.POR_COMENZAR,
    privacy=LeaguePrivacy.PUBLICA,
):
    league = League(
        name=name,
        match_duration=10,
        max_clubs=8,
        state=state,
        privacy=privacy,
        password_hash=(
            "test_hash"
            if privacy == LeaguePrivacy.PRIVADA
            else None
        ),
        creator_id=creator.id,
    )

    db.add(league)
    db.flush()

    return league


def test_get_visible_leagues_returns_empty_list(db):
    result = get_visible_leagues(db)

    assert result == []


def test_get_visible_leagues_filters_by_state(db, clubs):
    pending = create_league(
        db,
        clubs[0],
        "Pending League",
        state=LeagueState.POR_COMENZAR,
    )

    started = create_league(
        db,
        clubs[0],
        "Started League",
        state=LeagueState.INICIADA,
    )

    create_league(
        db,
        clubs[0],
        "Finished League",
        state=LeagueState.FINALIZADA,
    )

    result = get_visible_leagues(db)

    assert [league.id for league in result] == [
        pending.id,
        started.id,
    ]


def test_get_visible_leagues_includes_public_and_private(db, clubs):
    public = create_league(
        db,
        clubs[0],
        "Public League",
        privacy=LeaguePrivacy.PUBLICA,
    )

    private = create_league(
        db,
        clubs[0],
        "Private League",
        privacy=LeaguePrivacy.PRIVADA,
    )

    result = get_visible_leagues(db)

    assert {league.id for league in result} == {
        public.id,
        private.id,
    }


def test_get_visible_leagues_ordered_by_id(db, clubs):
    first = create_league(
        db,
        clubs[0],
        "First League",
    )

    second = create_league(
        db,
        clubs[0],
        "Second League",
    )

    third = create_league(
        db,
        clubs[0],
        "Third League",
    )

    result = get_visible_leagues(db)

    assert [league.id for league in result] == [
        first.id,
        second.id,
        third.id,
    ]


def test_get_visible_leagues_loads_participations(db, clubs):
    league_with_participants = create_league(
        db,
        clubs[0],
        "League With Participants",
    )

    league_without_participants = create_league(
        db,
        clubs[0],
        "League Without Participants",
    )

    for club in clubs[:2]:
        roster = Roster(
            club_id=club.id,
            formation=Formation.DEFENSIVE,
        )

        db.add(roster)
        db.flush()

        participation = LeagueParticipation(
            league_id=league_with_participants.id,
            club_id=club.id,
            roster_id=roster.id,
        )

        db.add(participation)

    db.flush()

    # Clear previously loaded relationships so the query
    # must retrieve the current database state.
    db.expire_all()

    result = get_visible_leagues(db)

    leagues_by_id = {
        league.id: league
        for league in result
    }

    assert len(
        leagues_by_id[
            league_with_participants.id
        ].league_participations
    ) == 2

    assert len(
        leagues_by_id[
            league_without_participants.id
        ].league_participations
    ) == 0