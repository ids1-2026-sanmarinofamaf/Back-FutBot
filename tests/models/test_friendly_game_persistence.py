import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base

from app.models.user import User
from app.models.roster import Roster, Formation
from app.models.player_on_roster import PlayerOnRoster
from app.models.friendly_game import (FriendlyGame, FriendlyGameState)
from app.models.friendly_game_participation import (
    FriendlyGameParticipation,
    FriendlyGameRole,
)
from sqlalchemy.exc import IntegrityError

from tests.models.stubs import Club, Player, Behavior


engine = create_engine("sqlite+pysqlite:///:memory:")

Session = sessionmaker(bind=engine)


def test_friendly_game_is_persisted_and_retrieved_with_relations():
    Base.metadata.create_all(
        engine,
        tables=[
            User.__table__,
            Club.__table__,
            Player.__table__,
            Behavior.__table__,
            Roster.__table__,
            PlayerOnRoster.__table__,
            FriendlyGame.__table__,
            FriendlyGameParticipation.__table__,
        ],
    )

    session = Session()

    try:
        # create users and rosters and persist
        user1 = User(
            id=1,
            email="user1@test.com",
            hash_passwd="hash1",
        )

        user2 = User(
            id=2,
            email="user2@test.com",
            hash_passwd="hash2",
        )

        club1 = Club(id=1)
        club2 = Club(id=2)

        roster1 = Roster(
            id=1,
            club_id=1,
            formation=Formation.DEFENSIVE,
        )

        roster2 = Roster(
            id=2,
            club_id=2,
            formation=Formation.OFFENSIVE,
        )

        session.add_all([
            user1,
            user2,
            club1,
            club2,
            roster1,
            roster2,
        ])

        session.commit()

    finally:
        #always close
        session.close()


    session = Session()

    try:
        # create friendlyGame and friendlyGameParticipations and perisist
        game = FriendlyGame(
            duration=15,
            creator_id=1,
            state=FriendlyGameState.POR_COMENZAR,
        )

        game.participations = [
            FriendlyGameParticipation(
                club_id=1,
                roster_id=1,
                role=FriendlyGameRole.CREATOR,
            ),
            FriendlyGameParticipation(
                club_id=2,
                roster_id=2,
                role=FriendlyGameRole.GUEST,
            ),
        ]

        session.add(game)
        session.commit()

        game_id = game.id

    finally:
        session.close()

    session = Session()

    try:
        # recover friendlyGame and verify data and relations
        saved_game = session.get(FriendlyGame, game_id)

        assert saved_game is not None

        assert saved_game.duration == 15
        assert saved_game.state == FriendlyGameState.POR_COMENZAR

        assert saved_game.creator_id == 1
        assert saved_game.creator.id == 1

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
            (1, 1, FriendlyGameRole.CREATOR),
            (2, 2, FriendlyGameRole.GUEST),
        }

        for participation in saved_game.participations:
            assert participation.club is not None
            assert participation.roster is not None

        saved_game.state = FriendlyGameState.JUGANDO
        session.commit()

    finally:
        session.close()

    session = Session()

    try:
        # recover friendlyGame again and verify that state change was persisted
        saved_game = session.get(FriendlyGame, game_id)

        assert saved_game is not None
        assert saved_game.state == FriendlyGameState.JUGANDO

    finally:
        session.close()


def test_friendly_game_rejects_third_participant_on_commit():
    session = Session()

    try:
        game = FriendlyGame(
            duration=15,
            creator_id=1,
            state=FriendlyGameState.POR_COMENZAR,
        )

        game.participations = [
            FriendlyGameParticipation(
                club_id=1,
                roster_id=1,
                role=FriendlyGameRole.CREATOR,
            ),
            FriendlyGameParticipation(
                club_id=2,
                roster_id=2,
                role=FriendlyGameRole.GUEST,
            ),
            FriendlyGameParticipation(
                club_id=3,
                roster_id=3,
                role=FriendlyGameRole.GUEST,
            ),
        ]

        session.add(game)

        with pytest.raises(IntegrityError):
            session.commit()

        session.rollback()

    finally:
        session.close()

    engine.dispose()