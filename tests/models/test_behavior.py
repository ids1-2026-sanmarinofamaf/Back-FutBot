import pytest

from sqlalchemy import Column, Integer, Table, create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.user import User
from app.models.club import Club
from app.models.behavior import Behavior
from app.models.roster import Roster, Formation
from app.models.player_on_roster import PlayerOnRoster, RosterSlot


BEHAVIOR_CODE = """def play(ctx):
    if ctx.ball_in_range():
        return kick(ctx.opponent_goal(), 1.0)
    return move_to(ctx.ball_position(), 1.0)
"""


@pytest.fixture
def session():
    """In-memory database with the tables needed by Behavior and its relations."""
    engine = create_engine("sqlite+pysqlite:///:memory:")

    # The Player model is not implemented yet, but players_on_roster.player_id
    # references "players". A minimal stub table is registered while the test
    # runs and removed afterwards. Once Player exists, this stub is skipped.
    players_stub = None
    if "players" not in Base.metadata.tables:
        players_stub = Table("players", Base.metadata, Column("id", Integer, primary_key=True))

    Base.metadata.create_all(
        engine,
        tables=[
            User.__table__,
            Club.__table__,
            Behavior.__table__,
            Base.metadata.tables["players"],
            Roster.__table__,
            PlayerOnRoster.__table__,
        ],
    )

    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()

    if players_stub is not None:
        Base.metadata.remove(players_stub)


@pytest.fixture
def club(session):
    user = User(email="user@test.com", hash_passwd="hash")
    club = Club(user=user, name="Club Test")
    session.add(club)
    session.commit()
    return club


def make_player_on_roster(player_id: int, behavior: Behavior) -> PlayerOnRoster:
    return PlayerOnRoster(
        player_id=player_id,
        is_starter=True,
        slot=RosterSlot.CENTER,
        initial_behavior=behavior,
    )


def test_behavior_is_created_and_persisted(session, club):
    behavior = Behavior(name="Delantero", code=BEHAVIOR_CODE, club=club)
    session.add(behavior)
    session.commit()

    assert behavior.id is not None
    assert session.get(Behavior, behavior.id) is not None


def test_behavior_requires_name_and_code(session, club):
    session.add(
        Behavior(
            code=BEHAVIOR_CODE,
            club=club,
        )
    )

    with pytest.raises(IntegrityError):
        session.commit()

    session.rollback()

    session.add(
        Behavior(
            name="Delantero",
            club=club,
        )
    )

    with pytest.raises(IntegrityError):
        session.commit()

    session.rollback()


def test_behavior_name_and_code_are_stored_and_retrieved(session, club):
    long_code = BEHAVIOR_CODE * 50  # longer than a String(255) column
    behavior = Behavior(name="Delantero", code=long_code, club=club)
    session.add(behavior)
    session.commit()
    behavior_id = behavior.id

    session.expire_all()
    stored = session.get(Behavior, behavior_id)

    assert stored.name == "Delantero"
    assert stored.code == long_code


def test_behavior_is_associated_with_its_club(session, club):
    behavior = Behavior(name="Defensor", code=BEHAVIOR_CODE, club=club)
    session.add(behavior)
    session.commit()

    session.expire_all()
    stored = session.get(Behavior, behavior.id)

    assert stored.club_id == club.id
    assert stored.club.name == "Club Test"
    assert stored in stored.club.behaviors


def test_club_can_have_many_behaviors(session, club):
    club.behaviors = [
        Behavior(name="Delantero", code=BEHAVIOR_CODE),
        Behavior(name="Defensor", code=BEHAVIOR_CODE),
    ]
    session.commit()

    session.expire_all()
    stored_club = session.get(Club, club.id)

    assert sorted(b.name for b in stored_club.behaviors) == ["Defensor", "Delantero"]


def test_behavior_is_associated_with_one_or_more_players_on_roster(session, club):
    behavior = Behavior(name="Delantero", code=BEHAVIOR_CODE, club=club)
    session.add(behavior)
    roster = Roster(club_id=club.id, formation=Formation.OFFENSIVE)
    roster.players = [
        make_player_on_roster(1, behavior),
        make_player_on_roster(2, behavior),
    ]
    session.add(roster)
    session.commit()
    behavior_id = behavior.id

    session.expire_all()
    stored = session.get(Behavior, behavior_id)

    assert sorted(p.player_id for p in stored.players_on_roster) == [1, 2]
    for player in stored.players_on_roster:
        assert player.initial_behavior_id == behavior_id
        assert player.initial_behavior is stored


def test_behavior_code_is_reachable_from_player_on_roster(session, club):
    behavior = Behavior(name="Delantero", code=BEHAVIOR_CODE, club=club)
    session.add(behavior)
    roster = Roster(club_id=club.id, formation=Formation.OFFENSIVE)
    roster.players = [make_player_on_roster(1, behavior)]
    session.add(roster)
    session.commit()
    player_id = roster.players[0].id

    session.expire_all()
    player = session.get(PlayerOnRoster, player_id)

    assert player.initial_behavior.code == BEHAVIOR_CODE


def test_default_behavior_can_exist_without_club(session):
    behavior = Behavior(
        name="Attacker",
        code="def play():\n    return wait()",
        club_id=None,
        is_default=True,
    )

    session.add(behavior)
    session.commit()

    stored = session.get(Behavior, behavior.id)

    assert stored is not None
    assert stored.club_id is None
    assert stored.is_default is True


def test_regular_behavior_can_belong_to_club(session, club):
    behavior = Behavior(
        name="Custom",
        code="def play():\n    return wait()",
        club=club,
        is_default=False,
    )

    session.add(behavior)
    session.commit()

    assert behavior.club_id == club.id
    assert behavior.is_default is False


def test_non_default_behavior_requires_club(session):
    behavior = Behavior(
        name="Custom",
        code=BEHAVIOR_CODE,
        is_default=False,
    )

    session.add(behavior)

    with pytest.raises(IntegrityError):
        session.commit()


def test_default_behavior_cannot_belong_to_club(session, club):
    behavior = Behavior(
        name="Attacker",
        code=BEHAVIOR_CODE,
        club=club,
        is_default=True,
    )

    session.add(behavior)

    with pytest.raises(IntegrityError):
        session.commit()