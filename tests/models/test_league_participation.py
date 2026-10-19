import pytest

from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.user import User
from app.models.club import Club
from app.models.league import League, LeaguePrivacy
from app.models.league_participation import LeagueParticipation
from app.models.roster import Roster, Formation


@pytest.fixture
def session():
    engine = create_engine("sqlite+pysqlite:///:memory:")

    # SQLite ignores foreign keys (and ON DELETE CASCADE) unless enabled per connection
    @event.listens_for(engine, "connect")
    def enable_sqlite_fks(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    tables = [
        User.__table__,
        Club.__table__,
        Roster.__table__,
        League.__table__,
        LeagueParticipation.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)

    db = sessionmaker(bind=engine)()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine, tables=list(reversed(tables)))
        engine.dispose()


def make_club(session, n):
    user = User(email=f"user{n}@test.com", hash_passwd="hash")
    club = Club(user=user, name=f"Club {n}")
    session.add(club)
    session.commit()
    return club


@pytest.fixture
def club(session):
    return make_club(session, 1)


@pytest.fixture
def league(session, club):
    league = League(
        name="Liga Test",
        match_duration=90,
        max_clubs=5,
        privacy=LeaguePrivacy.PUBLICA,
        creator=club,
    )
    session.add(league)
    session.commit()
    return league


@pytest.fixture
def roster(session, club):
    roster = Roster(
        club_id=club.id,
        formation=Formation.OFFENSIVE,
    )
    session.add(roster)
    session.commit()
    return roster


def test_participation_is_persisted_with_defaults(session, league, club, roster):
    session.add(LeagueParticipation(league=league, club=club, roster=roster))
    session.commit()

    session.expire_all()
    saved = session.get(LeagueParticipation, (league.id, club.id))

    assert saved is not None
    assert saved.league_id == league.id
    assert saved.club_id == club.id
    # los defaults de la tabla
    assert saved.points == 0
    assert saved.matches_played == 0
    assert saved.matches_won == 0
    assert saved.matches_drawn == 0
    assert saved.matches_lost == 0
    assert saved.goals_for == 0
    assert saved.goals_against == 0


def test_participation_stores_stats(session, league, club, roster):
    session.add(LeagueParticipation(
        league=league,
        club=club,
        roster=roster,
        matches_played=4,
        matches_won=2,
        matches_drawn=1,
        matches_lost=1,
        points=7,          # 3*2 + 1
        goals_for=6,
        goals_against=3,
    ))
    session.commit()

    session.expire_all()
    saved = session.get(LeagueParticipation, (league.id, club.id))

    assert saved.matches_played == 4
    assert saved.points == 7
    assert saved.goals_for == 6
    assert saved.goals_against == 3


def test_relationships_link_league_and_club(session, league, club, roster):
    other = make_club(session, 2)

    other_roster = Roster(
        club_id=other.id,
        formation=Formation.OFFENSIVE,
    )
    session.add(other_roster)
    session.flush()

    session.add_all([
        LeagueParticipation(league=league, club=club, roster=roster),
        LeagueParticipation(league=league, club=other, roster=other_roster),
    ])
    session.commit()

    session.expire_all()

    assert {p.club_id for p in league.league_participations} == {club.id, other.id}
    assert len(club.league_participations) == 1
    assert club.league_participations[0].league_id == league.id


def test_club_cannot_join_same_league_twice(session, league, club, roster):
    league_id, club_id = league.id, club.id
    roster_id = roster.id
    session.add(LeagueParticipation(league_id=league_id,club_id=club_id,roster_id=roster_id))
    session.commit()

    # sacamos la primera de la sesión para que el duplicado llegue a la base
    session.expunge_all()
    session.add(LeagueParticipation(league_id=league_id,club_id=club_id,roster_id=roster_id))
    with pytest.raises(IntegrityError):
        session.commit()


def test_negative_stats_are_rejected(session, league, club, roster):
    session.add(LeagueParticipation(league=league, club=club, roster=roster, goals_for=-1))

    with pytest.raises(IntegrityError):
        session.commit()


def test_matches_played_must_match_results(session, league, club, roster):
    # 2 + 0 + 0 != 3
    session.add(LeagueParticipation(
        league=league, club=club, roster=roster,
        matches_played=3, matches_won=2, points=6,
    ))

    with pytest.raises(IntegrityError):
        session.commit()


def test_points_must_follow_3_1_0_rule(session, league, club, roster):
    # 1 ganado + 1 empatado = 4 puntos, no 5
    session.add(LeagueParticipation(
        league=league, club=club, roster=roster,
        matches_played=2, matches_won=1, matches_drawn=1, points=5,
    ))

    with pytest.raises(IntegrityError):
        session.commit()


def test_deleting_league_deletes_its_participations(session, league, club, roster):
    session.add(LeagueParticipation(league=league, club=club, roster=roster))
    session.commit()
    league_id, club_id = league.id, club.id

    session.delete(league)
    session.commit()

    assert session.get(LeagueParticipation, (league_id, club_id)) is None