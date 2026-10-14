import pytest

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.user import User
from app.models.club import Club
from app.models.league import League, LeagueState, LeaguePrivacy
from app.models.league_participation import LeagueParticipation


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
