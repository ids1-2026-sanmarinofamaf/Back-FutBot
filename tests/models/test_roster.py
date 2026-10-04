from app.models.roster import Roster, Formation
from app.models.player_on_roster import PlayerOnRoster, RosterSlot


def test_roster_and_players_on_roster_are_created_correctly():

    # create a roster and its players directly in memory.
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

    # verify that the roster was created with the expected data.
    assert roster.club_id == 1
    assert roster.formation == Formation.DEFENSIVE

    assert len(roster.players) == 6

    # separate starters and substitutes to verify the roster structure.
    starters = [
        player
        for player in roster.players
        if player.is_starter
    ]

    substitutes = [
        player
        for player in roster.players
        if not player.is_starter
    ]

    assert len(starters) == 3
    assert len(substitutes) == 3

    # verify that all expected players are part of the roster.
    assert {
        player.player_id
        for player in roster.players
    } == {1, 2, 3, 4, 5, 6}

    # verify that starter slots were assigned correctly.
    assert {
        player.slot
        for player in starters
    } == {
        RosterSlot.LEFT,
        RosterSlot.CENTER,
        RosterSlot.RIGHT,
    }

    # verify that initial behavior was assigned to starters.
    assert all(
        player.initial_behavior_id == 1
        for player in starters
    )

    # verify substitutes don't have a slot or an initial behavior.
    assert all(
        player.slot is None
        for player in substitutes
    )

    assert all(
        player.initial_behavior_id is None
        for player in substitutes
    )