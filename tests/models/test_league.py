from datetime import datetime, timedelta, timezone

import pytest

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from app.database import Base
from app.models.user import User
from app.models.club import Club
from app.models.league import League, LeagueState, LeaguePrivacy
from app.models.league_participation import LeagueParticipation
from app.models.match import Match, MatchState


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
        League.__table__,
        LeagueParticipation.__table__,
        Match.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)

    db = sessionmaker(bind=engine)()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine, tables=list(reversed(tables)))
        engine.dispose()


@pytest.fixture
def creator(session):
    # creator_id es FK a clubs, así que hace falta un club real
    user = User(email="creator@test.com", hash_passwd="hash")
    club = Club(user=user, name="Club Creador")
    session.add(club)
    session.commit()
    return club


def test_public_league_is_persisted(session, creator):
    league = League(
        name="Liga Publica",
        match_duration=90,
        max_clubs=5,
        privacy=LeaguePrivacy.PUBLICA,
        creator=creator,
    )
    session.add(league)
    session.commit()
    league_id = league.id

    # vaciamos la sesión para que el query lea de la base y no de memoria
    session.expire_all()
    saved = session.get(League, league_id)
    
    assert saved is not None
    assert saved.name == "Liga Publica"
    assert saved.match_duration == 90
    assert saved.max_clubs == 5
    assert saved.privacy == LeaguePrivacy.PUBLICA
    assert saved.password_hash is None
    assert saved.state == LeagueState.POR_COMENZAR   # default
    assert saved.creator_id == creator.id
    assert saved.last_completed_round == 0
    assert saved.break_ends_at is None


def test_private_league_stores_password(session, creator):
    league = League(
        name="Liga Privada",
        match_duration=60,
        max_clubs=4,
        privacy=LeaguePrivacy.PRIVADA,
        password_hash="hash_secreto",
        creator=creator,
    )
    session.add(league)
    session.commit()
    league_id = league.id

    session.expunge_all()
    saved = session.get(League, league_id)

    assert saved.privacy == LeaguePrivacy.PRIVADA
    assert saved.password_hash == "hash_secreto"


@pytest.fixture
def league(session, creator):
    league = League(
        name="Liga Test",
        match_duration=90,
        max_clubs=4,
        privacy=LeaguePrivacy.PUBLICA,
        creator=creator,
    )
    session.add(league)
    session.commit()
    return league


def test_league_progress_is_persisted(session, league):
    break_end = datetime(2026, 11, 2, 19, 0, tzinfo=timezone.utc)

    league.last_completed_round = 2
    league.break_ends_at = break_end
    session.commit()

    session.expire_all()
    saved = session.get(League, league.id)

    assert saved.last_completed_round == 2
    assert saved.break_ends_at == break_end.replace(tzinfo=None)


def test_league_rejects_negative_completed_round(session, league):
    league.last_completed_round = -1

    with pytest.raises(IntegrityError):
        session.commit()

    session.rollback()


def test_match_without_result_is_persisted(session, league):
    match = Match(id=100, league_id=league.id, round=1)

    session.add(match)
    session.commit()
    session.expire_all()

    saved = session.get(Match, 100)

    assert saved.state == MatchState.POR_COMENZAR
    assert saved.home_goals is None
    assert saved.away_goals is None


@pytest.mark.parametrize(
    "home_goals, away_goals",
    [
        (3, 1),
        (0, 0),
    ],
)
def test_finished_match_result_is_persisted(
    session, league, home_goals, away_goals
):
    match = Match(
        id=101,
        league_id=league.id,
        round=1,
        state=MatchState.FINALIZADO,
        home_goals=home_goals,
        away_goals=away_goals,
    )

    session.add(match)
    session.commit()
    session.expire_all()

    saved = session.get(Match, 101)

    assert saved.state == MatchState.FINALIZADO
    assert saved.home_goals == home_goals
    assert saved.away_goals == away_goals


@pytest.mark.parametrize(
    "home_goals, away_goals",
    [
        (-1, 2),
        (2, -1),
    ],
)
def test_match_rejects_negative_goals(
    session, league, home_goals, away_goals
):
    match = Match(
        id=102,
        league_id=league.id,
        state=MatchState.FINALIZADO,
        home_goals=home_goals,
        away_goals=away_goals,
    )

    session.add(match)

    with pytest.raises(IntegrityError):
        session.commit()

    session.rollback()


@pytest.mark.parametrize(
    "home_goals, away_goals",
    [
        (None, None),
        (2, None),
        (None, 1),
    ],
)
def test_finished_match_requires_both_scores(
    session, league, home_goals, away_goals
):
    match = Match(
        id=103,
        league_id=league.id,
        state=MatchState.FINALIZADO,
        home_goals=home_goals,
        away_goals=away_goals,
    )

    session.add(match)

    with pytest.raises(IntegrityError):
        session.commit()

    session.rollback()


@pytest.mark.parametrize(
    "state",
    [
        MatchState.POR_COMENZAR,
        MatchState.JUGANDO,
    ]
)
def test_unfinished_match_rejects_score(session, league, state):
    match = Match(
        id=104,
        league_id=league.id,
        state=state,
        home_goals=2,
        away_goals=1,
    )

    session.add(match)

    with pytest.raises(IntegrityError):
        session.commit()

    session.rollback()


def test_interrupted_match_can_be_reset(session, league):
    match = Match(
        id=105,
        league_id=league.id,
        round=1,
        state=MatchState.FINALIZADO,
        home_goals=2,
        away_goals=1,
    )

    session.add(match)
    session.commit()

    match.state = MatchState.POR_COMENZAR
    match.home_goals = None
    match.away_goals = None

    session.commit()
    session.expire_all()

    saved = session.get(Match, 105)

    assert saved.state == MatchState.POR_COMENZAR
    assert saved.home_goals is None
    assert saved.away_goals is None


def test_match_without_league_does_not_require_score(session):
    match = Match(
        id=106,
        state=MatchState.FINALIZADO,
    )

    session.add(match)
    session.commit()
    session.expire_all()

    saved = session.get(Match, 106)

    assert saved.home_goals is None
    assert saved.away_goals is None


def test_match_state_transitions_are_persisted(session, league):
    match = Match(
        id=200,
        league_id=league.id,
        round=1,
    )
    session.add(match)
    session.commit()

    match.state = MatchState.JUGANDO
    session.commit()

    session.expire_all()
    saved = session.get(Match, 200)

    assert saved.state == MatchState.JUGANDO
    assert saved.home_goals is None
    assert saved.away_goals is None

    saved.state = MatchState.FINALIZADO
    saved.home_goals = 2
    saved.away_goals = 1
    session.commit()

    session.expire_all()
    saved = session.get(Match, 200)

    assert saved.state == MatchState.FINALIZADO
    assert saved.home_goals == 2
    assert saved.away_goals == 1


@pytest.mark.parametrize(
    "state",
    [
        MatchState.POR_COMENZAR,
        MatchState.JUGANDO,
    ],
)
def test_unfinished_match_rejects_partial_score(session, league, state):
    match = Match(
        id=201,
        league_id=league.id,
        state=state,
        home_goals=1,
        away_goals=None,
    )

    session.add(match)

    with pytest.raises(IntegrityError):
        session.commit()

    session.rollback()


def test_league_break_can_be_cleared(session, league):
    league.break_ends_at = datetime(
        2026, 11, 2, 19, 0, tzinfo=timezone.utc
    )
    session.commit()

    league.break_ends_at = None
    session.commit()

    session.expire_all()
    saved = session.get(League, league.id)

    assert saved.break_ends_at is None