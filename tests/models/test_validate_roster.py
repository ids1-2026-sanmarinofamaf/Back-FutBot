import pytest

from app.models.player_on_roster import PlayerOnRoster, RosterSlot
from tests.models.stubs import Club, Player, Behavior


def test_valid_roster(valid_roster):
    valid_roster.validate_roster()

def test_roster_rejects_less_than_six_players(valid_roster):
    valid_roster.players.pop()

    with pytest.raises(ValueError,
        match="A roster must have exactly 6 players",
    ):
        valid_roster.validate_roster()

def test_roster_rejects_more_than_six_players(valid_roster):
    valid_roster.players.append(
        PlayerOnRoster(
            player_id=7,
            is_starter=False,
            slot=None,
            initial_behavior_id=None,
        )
    )

    with pytest.raises(ValueError,
        match="A roster must have exactly 6 players",
    ):
        valid_roster.validate_roster()

def test_roster_rejects_wrong_number_of_starters(valid_roster):
    valid_roster.players[3].is_starter = True

    with pytest.raises(ValueError,
        match="A roster must have exactly 3 starters",
    ):
        valid_roster.validate_roster()

def test_roster_rejects_duplicate_players(valid_roster):
    valid_roster.players[5].player_id = (
        valid_roster.players[0].player_id
    )

    with pytest.raises(ValueError,
        match="A roster cannot contain duplicate players",
    ):
        valid_roster.validate_roster()

def test_roster_rejects_starter_without_slot(valid_roster):
    valid_roster.players[0].slot = None

    with pytest.raises(ValueError,
        match="A starter must have a roster slot",
    ):
        valid_roster.validate_roster()

def test_roster_rejects_starter_without_behavior(valid_roster):
    valid_roster.players[0].initial_behavior_id = None

    with pytest.raises(ValueError,
        match="A starter must have an initial behavior",
    ):
        valid_roster.validate_roster()

def test_roster_rejects_substitute_with_slot(valid_roster):
    valid_roster.players[3].slot = RosterSlot.LEFT

    with pytest.raises(ValueError,
        match="A substitute cannot have a roster slot",
    ):
        valid_roster.validate_roster()

def test_roster_rejects_substitute_with_behavior(valid_roster):
    valid_roster.players[3].initial_behavior_id = 1

    with pytest.raises(ValueError,
        match="A substitute cannot have an initial behavior",
    ):
        valid_roster.validate_roster()

def test_roster_rejects_duplicate_starter_slots(valid_roster):
    valid_roster.players[1].slot = RosterSlot.LEFT

    with pytest.raises(
        ValueError,
        match="Starter roster slots must be unique",
    ):
        valid_roster.validate_roster()