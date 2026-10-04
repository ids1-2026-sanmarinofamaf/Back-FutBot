import pytest

from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.database import Base

from app.models.user import User
from app.models.club import Club
from app.models.roster import Roster, Formation
from app.models.friendly_game import FriendlyGame, FriendlyGameState
from app.models.friendly_game_participation import (
    FriendlyGameParticipation,
    FriendlyGameRole,
)


@pytest.fixture
def session():
    """
    Create an isolated in-memory database for each test.
    Only the tables required by FriendlyGame persistence tests are created.
    """
    engine = create_engine("sqlite+pysqlite:///:memory:")

    Base.metadata.create_all(
        engine,
        tables=[
            User.__table__,
            Club.__table__,
            Roster.__table__,
            FriendlyGame.__table__,
            FriendlyGameParticipation.__table__,
        ],
    )

    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        yield db
    finally:
        db.close()

        Base.metadata.drop_all(
            engine,
            tables=[
                FriendlyGameParticipation.__table__,
                FriendlyGame.__table__,
                Roster.__table__,
                Club.__table__,
                User.__table__,
            ],
        )

        engine.dispose()


def create_user_club_and_roster(
    session,
    user_id: int,
    club_id: int,
    roster_id: int,
    formation: Formation,
):
    """Create and persist the minimum objects required for a participation."""

    user = User(
        id=user_id,
        email=f"user{user_id}@test.com",
        hash_passwd=f"hash{user_id}",
    )

    club = Club(
        id=club_id,
        user_id=user_id,
        name=f"Club {club_id}",
    )

    roster = Roster(
        id=roster_id,
        club_id=club_id,
        formation=formation,
    )

    session.add_all([
        user,
        club,
        roster,
    ])

    session.flush()

    return user, club, roster


def test_friendly_game_is_persisted_and_retrieved_with_relations(session):
    
    _, club1, roster1 = create_user_club_and_roster(
        session=session,
        user_id=1,
        club_id=1,
        roster_id=1,
        formation=Formation.DEFENSIVE,
    )

    _, club2, roster2 = create_user_club_and_roster(
        session=session,
        user_id=2,
        club_id=2,
        roster_id=2,
        formation=Formation.OFFENSIVE,
    )

    game = FriendlyGame(
        duration=15,
        creator_id=club1.id,
        state=FriendlyGameState.POR_COMENZAR,
    )

    game.participations = [
        FriendlyGameParticipation(
            club_id=club1.id,
            roster_id=roster1.id,
            role=FriendlyGameRole.CREATOR,
        ),
        FriendlyGameParticipation(
            club_id=club2.id,
            roster_id=roster2.id,
            role=FriendlyGameRole.GUEST,
        ),
    ]

    
    session.add(game)
    session.commit()

    game_id = game.id

    # Remove objects from the SQLAlchemy session so the next access
    # actually reloads them from the database.
    session.expire_all()

    saved_game = session.get(FriendlyGame, game_id)

    
    assert saved_game is not None

    assert saved_game.duration == 15
    assert saved_game.state == FriendlyGameState.POR_COMENZAR

    assert saved_game.creator_id == club1.id
    assert saved_game.creator.id == club1.id

    assert len(saved_game.participations) == 2

    participations = {
        (
            participation.club_id,
            participation.roster_id,
            participation.role,
        )
        for participation in saved_game.participations
    }

    assert participations == {
        (
            club1.id,
            roster1.id,
            FriendlyGameRole.CREATOR,
        ),
        (
            club2.id,
            roster2.id,
            FriendlyGameRole.GUEST,
        ),
    }

    for participation in saved_game.participations:
        assert participation.club is not None
        assert participation.roster is not None


def test_friendly_game_state_change_is_persisted(session):
    
    _, club, _ = create_user_club_and_roster(
        session=session,
        user_id=1,
        club_id=1,
        roster_id=1,
        formation=Formation.DEFENSIVE,
    )

    game = FriendlyGame(
        duration=15,
        creator_id=club.id,
        state=FriendlyGameState.POR_COMENZAR,
    )

    session.add(game)
    session.commit()

    game_id = game.id

    
    game.state = FriendlyGameState.JUGANDO
    session.commit()

    session.expire_all()

    saved_game = session.get(FriendlyGame, game_id)

    #
    assert saved_game is not None
    assert saved_game.state == FriendlyGameState.JUGANDO


def test_friendly_game_rejects_more_than_one_participant_with_same_role(session):
    
    _, club1, roster1 = create_user_club_and_roster(
        session=session,
        user_id=1,
        club_id=1,
        roster_id=1,
        formation=Formation.DEFENSIVE,
    )

    _, club2, roster2 = create_user_club_and_roster(
        session=session,
        user_id=2,
        club_id=2,
        roster_id=2,
        formation=Formation.OFFENSIVE,
    )

    _, club3, roster3 = create_user_club_and_roster(
        session=session,
        user_id=3,
        club_id=3,
        roster_id=3,
        formation=Formation.DEFENSIVE,
    )

    game = FriendlyGame(
        duration=15,
        creator_id=club1.id,
        state=FriendlyGameState.POR_COMENZAR,
    )

    game.participations = [
        FriendlyGameParticipation(
            club_id=club1.id,
            roster_id=roster1.id,
            role=FriendlyGameRole.CREATOR,
        ),
        FriendlyGameParticipation(
            club_id=club2.id,
            roster_id=roster2.id,
            role=FriendlyGameRole.GUEST,
        ),
        FriendlyGameParticipation(
            club_id=club3.id,
            roster_id=roster3.id,
            role=FriendlyGameRole.GUEST,
        ),
    ]

    session.add(game)

   
    with pytest.raises(IntegrityError):
        session.commit()

    session.rollback()


def test_friendly_game_rejects_same_club_twice(session):
    
    _, club1, roster1 = create_user_club_and_roster(
        session=session,
        user_id=1,
        club_id=1,
        roster_id=1,
        formation=Formation.DEFENSIVE,
    )

    roster2 = Roster(
        id=2,
        club_id=club1.id,
        formation=Formation.OFFENSIVE,
    )

    session.add(roster2)
    session.flush()

    game = FriendlyGame(
        duration=15,
        creator_id=club1.id,
    )

    game.participations = [
        FriendlyGameParticipation(
            club_id=club1.id,
            roster_id=roster1.id,
            role=FriendlyGameRole.CREATOR,
        ),
        FriendlyGameParticipation(
            club_id=club1.id,
            roster_id=roster2.id,
            role=FriendlyGameRole.GUEST,
        ),
    ]

    session.add(game)

    
    with pytest.raises(IntegrityError):
        session.commit()

    session.rollback()


def test_friendly_game_rejects_non_positive_duration(session):
    
    _, club, _ = create_user_club_and_roster(
        session=session,
        user_id=1,
        club_id=1,
        roster_id=1,
        formation=Formation.DEFENSIVE,
    )

    game = FriendlyGame(
        duration=0,
        creator_id=club.id,
    )

    session.add(game)

    
    with pytest.raises(IntegrityError):
        session.commit()

    session.rollback()