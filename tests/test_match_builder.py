from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

from app.models.roster import Formation
from app.models.player_on_roster import RosterSlot
from app.services import match_builder


@pytest.fixture
def roster():
    slots = [
        RosterSlot.LEFT,
        RosterSlot.CENTER,
        RosterSlot.RIGHT,
    ]

    players = [
        SimpleNamespace(
            player_id=i,
            is_starter=i <= 3,
            slot=slots[i - 1] if i <= 3 else None,
            initial_behavior_id=100 + i if i <= 3 else None,
        )
        for i in range(1, 7)
    ]

    return SimpleNamespace(
        id=10,
        club_id=20,
        formation=Formation.DEFENSIVE,
        players=players,
    )


@pytest.fixture
def mock_players(monkeypatch):
    # Different attributes help detect incorrect player mappings.
    players = {
        i: SimpleNamespace(
            id=i,
            power=40 + i,
            agility=45 + i,
            control=50 + i,
            speed=55 + i,
            strength=60 + i,
        )
        for i in range(1, 7)
    }

    lookup = Mock(
        side_effect=lambda db, player_id: players.get(player_id)
    )

    monkeypatch.setattr(
        match_builder.player_repository,
        "get_by_id",
        lookup,
    )

    return lookup


def test_create_starter_player(roster, mock_players):
    db = Mock()

    player = match_builder._create_player_in_match(
        db=db,
        player_on_roster=roster.players[0],
        formation=roster.formation,
        mirror_position=False,
    )

    assert player.player_id == 1
    assert player.is_on_field is True

    assert player.position == (8.0, 5.0)
    assert player.starting_position == (8.0, 5.0)
    assert player.velocity == (0.0, 0.0)

    assert player.current_behavior_id == 101

    assert player.power == 41
    assert player.agility == 46
    assert player.control == 51
    assert player.speed == 56
    assert player.strength == 61

    mock_players.assert_called_once_with(db, 1)


def test_create_substitute_player(roster, mock_players):
    player = match_builder._create_player_in_match(
        db=Mock(),
        player_on_roster=roster.players[3],
        formation=roster.formation,
        mirror_position=False,
    )

    assert player.player_id == 4
    assert player.is_on_field is False

    assert player.position == (0.0, 0.0)
    assert player.starting_position is None
    assert player.velocity == (0.0, 0.0)

    assert player.current_behavior_id is None


@pytest.mark.parametrize(
    "formation, mirror_position, expected_position",
    [
        (Formation.DEFENSIVE, False, (8.0, 5.0)),
        (Formation.DEFENSIVE, True, (32.0, 5.0)),
        (Formation.OFFENSIVE, False, (16.0, 5.0)),
        (Formation.OFFENSIVE, True, (24.0, 5.0)),
    ],
)
def test_create_player_initial_position(
    roster,
    mock_players,
    formation,
    mirror_position,
    expected_position,
):
    player = match_builder._create_player_in_match(
        db=Mock(),
        player_on_roster=roster.players[0],
        formation=formation,
        mirror_position=mirror_position,
    )

    assert player.position == expected_position
    assert player.starting_position == expected_position


def test_create_match_participation(roster, mock_players):
    db = Mock()

    participation = match_builder.create_match_participation(
        db=db,
        roster=roster,
        mirror_position=True,
    )

    assert participation.club_id == 20
    assert participation.roster_id == 10
    assert participation.goals == 0

    assert len(participation.players) == 6

    players_by_id = {
        player.player_id: player
        for player in participation.players
    }

    assert set(players_by_id) == {1, 2, 3, 4, 5, 6}

    # All starters must be positioned on the mirrored side.
    assert players_by_id[1].position == (32.0, 5.0)
    assert players_by_id[2].position == (34.0, 10.0)
    assert players_by_id[3].position == (32.0, 15.0)

    for player_id in range(1, 7):
        player = players_by_id[player_id]

        # Verify each player retains their own attributes.
        assert player.power == 40 + player_id
        assert player.agility == 45 + player_id
        assert player.control == 50 + player_id
        assert player.speed == 55 + player_id
        assert player.strength == 60 + player_id

        if player_id <= 3:
            assert player.is_on_field is True
            assert player.current_behavior_id == 100 + player_id
        else:
            assert player.is_on_field is False
            assert player.current_behavior_id is None
            assert player.starting_position is None

    assert mock_players.call_args_list == [
        call(db, player_id)
        for player_id in range(1, 7)
    ]


def test_create_player_raises_if_player_not_found(
    roster,
    mock_players,
):
    mock_players.side_effect = lambda db, player_id: None

    with pytest.raises(
        ValueError,
        match="Player does not exist",
    ):
        match_builder._create_player_in_match(
            db=Mock(),
            player_on_roster=roster.players[0],
            formation=roster.formation,
            mirror_position=False,
        )
