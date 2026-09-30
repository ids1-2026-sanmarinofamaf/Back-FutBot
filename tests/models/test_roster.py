from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from tests.models.stubs import Club, Player, Behavior

from app.database import Base
from app.models.roster import Roster, Formation
from app.models.player_on_roster import PlayerOnRoster, RosterSlot


# test database in memory
engine = create_engine("sqlite+pysqlite:///:memory:")

# Session factory
Session = sessionmaker(bind=engine)

def test_roster_and_players_on_roster_are_stored_and_retrieved():

    # specify which tables we create for this test.
    Base.metadata.create_all(
        engine, tables=[
            Club.__table__,
            Player.__table__,
            Behavior.__table__,
            Roster.__table__,
            PlayerOnRoster.__table__,
        ],
    )

    # use the session and create objects for the database.
    session = Session()

    try:
        club = Club(id=1)
        players = [
            Player(id=1),
            Player(id=2),
            Player(id=3),
            Player(id=4),
            Player(id=5),
            Player(id=6),
        ]
        behavior = Behavior(id=1)

        session.add(club)
        session.add_all(players)
        session.add(behavior)

        session.commit()

    finally:
        session.close()  # always close session



    # create several sessions for greater robustness
    # in this session, we save the Roster and PlayerOnRoster to the database.
    session = Session()

    try:
        roster = Roster(
            club_id=1,
            formation=Formation.DEFENSIVE,
        )

        roster.players = [
            PlayerOnRoster(
                player_id=1,
                is_starter=True,
                slot=RosterSlot.LEFT,
                initial_behavior_id=1,
            ),
            PlayerOnRoster(
                player_id=2,
                is_starter=True,
                slot=RosterSlot.CENTER,
                initial_behavior_id=1,
            ),
            PlayerOnRoster(
                player_id=3,
                is_starter=True,
                slot=RosterSlot.RIGHT,
                initial_behavior_id=1,
            ),
            PlayerOnRoster(
                player_id=4,
                is_starter=False,
                slot=None,
                initial_behavior_id=None,
            ),
            PlayerOnRoster(
                player_id=5,
                is_starter=False,
                slot=None,
                initial_behavior_id=None,
            ),
            PlayerOnRoster(
                player_id=6,
                is_starter=False,
                slot=None,
                initial_behavior_id=None,
            ),
        ]

        session.add(roster)
        session.commit()

        roster_id = roster.id

    finally:
        session.close()

    # finally we try to retrieve from database

    session = Session()

    try:
        saved_roster = session.get(Roster, roster_id) # we verify that everything stored in the database can be correctly retrieved.

        assert saved_roster is not None
        assert saved_roster.club_id == 1
        assert saved_roster.formation == Formation.DEFENSIVE

        assert len(saved_roster.players) == 6

        starters = [
            player
            for player in saved_roster.players
            if player.is_starter
        ]

        substitutes = [
            player
            for player in saved_roster.players
            if not player.is_starter
        ]

        assert len(starters) == 3
        assert len(substitutes) == 3

        assert {
            player.player_id
            for player in saved_roster.players
        } == {1, 2, 3, 4, 5, 6}

    finally:
        session.close()

    # close all connections associated with the test database
    engine.dispose()