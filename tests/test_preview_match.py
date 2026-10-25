import pytest

from app.game.constants import (
    FIELD_CENTER,
    FIELD_WIDTH,
    TICS_PER_SECOND,
)
from app.game.formations import FORMATION_POSITIONS
from app.game.models.match import Match, MatchState
from app.game.preview_match import (
    create_preview_match,
    PREVIEW_DURATION_SECONDS,
    TEMPORARY_BEHAVIOR_ID,
    PREVIEW_PLAYER_ID,
    PLAYER_STATS,
)
from app.models.roster import Formation
from app.models.player_on_roster import RosterSlot


DEFAULT_IDS = {
    "Attacker": 100,
    "Midfielder": 200,
    "Defender": 300,
}


@pytest.fixture
def preview_match():
    return create_preview_match(
        behavior_teammate_1=10,
        behavior_teammate_2=20,
        default_behaviors_ids=DEFAULT_IDS,
    )


def test_preview_match_initial_state(preview_match):
    assert isinstance(preview_match, Match)
    assert preview_match.state == MatchState.NOT_STARTED
    assert preview_match.current_tick == 0
    assert preview_match.duration_ticks == (
        PREVIEW_DURATION_SECONDS * TICS_PER_SECOND
    )
    assert preview_match.ball.position == FIELD_CENTER
    assert preview_match.ball.velocity == (0.0, 0.0)


def test_preview_match_has_correct_players(preview_match):
    for participation in (
        preview_match.participation_a,
        preview_match.participation_b,
    ):
        assert len(participation.players) == 6

        starters = [p for p in participation.players if p.is_on_field]
        substitutes = [p for p in participation.players if not p.is_on_field]

        assert len(starters) == 3
        assert len(substitutes) == 3


def test_preview_match_assigns_test_behavior_to_center(preview_match):
    players = preview_match.participation_a.players

    assert players[0].current_behavior_id == 10
    assert players[1].current_behavior_id == TEMPORARY_BEHAVIOR_ID
    assert players[1].player_id == PREVIEW_PLAYER_ID
    assert players[2].current_behavior_id == 20


def test_preview_match_assigns_default_behavior_to_opponents(preview_match):
    players = preview_match.participation_b.players

    assert [p.current_behavior_id for p in players[:3]] == [
        DEFAULT_IDS["Defender"],
        DEFAULT_IDS["Midfielder"],
        DEFAULT_IDS["Attacker"],
    ]


def test_preview_match_uses_defensive_formation(preview_match):
    slots = (
        RosterSlot.LEFT,
        RosterSlot.CENTER,
        RosterSlot.RIGHT,
    )

    for index, slot in enumerate(slots):
        expected = FORMATION_POSITIONS[Formation.DEFENSIVE][slot]

        player_a = preview_match.participation_a.players[index]
        player_b = preview_match.participation_b.players[index]

        assert player_a.position == expected
        assert player_a.starting_position == expected

        mirrored = (FIELD_WIDTH - expected[0], expected[1])

        assert player_b.position == mirrored
        assert player_b.starting_position == mirrored


def test_preview_match_substitutes_are_inactive(preview_match):
    for participation in (
        preview_match.participation_a,
        preview_match.participation_b,
    ):
        for player in participation.players[3:]:
            assert player.is_on_field is False
            assert player.current_behavior_id is None
            assert player.starting_position is None


def test_preview_match_uses_fixed_player_stats(preview_match):
    for participation in (
        preview_match.participation_a,
        preview_match.participation_b,
    ):
        for player in participation.players:
            assert (
                player.power,
                player.agility,
                player.control,
                player.speed,
                player.strength,
            ) == (60, 60, 60, 60, 60)


def test_preview_matches_have_independent_state():
    first = create_preview_match(10, 20, DEFAULT_IDS)
    second = create_preview_match(10, 20, DEFAULT_IDS)

    first.participation_a.players[0].position = (12.0, 8.0)

    assert second.participation_a.players[0].position != (12.0, 8.0)


def test_preview_match_has_unique_player_ids(preview_match):
    players = (
        preview_match.participation_a.players
        + preview_match.participation_b.players
    )

    player_ids = [player.player_id for player in players]

    assert len(player_ids) == len(set(player_ids))


def test_preview_match_has_distinct_participations(preview_match):
    participation_a = preview_match.participation_a
    participation_b = preview_match.participation_b

    assert participation_a.club_id != participation_b.club_id
    assert participation_a.roster_id != participation_b.roster_id

    assert participation_a.goals == 0
    assert participation_b.goals == 0


def test_preview_match_allows_same_behavior_for_teammates():
    match = create_preview_match(
        behavior_teammate_1=101,
        behavior_teammate_2=101,
        default_behaviors_ids=DEFAULT_IDS,
    )

    players = match.participation_a.players

    assert players[0].current_behavior_id == 101
    assert players[2].current_behavior_id == 101