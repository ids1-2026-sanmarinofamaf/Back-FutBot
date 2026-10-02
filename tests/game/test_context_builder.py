"""
Unit test for context builder
"""
from math import isclose

import pytest

from app.game.constants import COLLISION_PENALTY, TIC_DURATION
from app.game.context_builder import (
    _effective_physical_value,
    _get_player_and_opponent_team,
    build_behavior_context,
)
from app.game.physics import (
    control_range,
    max_kick_force,
    max_move_speed,
)
from app.game.types import Period, Side


def test_get_player_and_opponent_team_returns_team_a_for_player_a(
    player_a_snapshot,
    match_snapshot,
):
    player_team, opponent_team = _get_player_and_opponent_team(
        player_a_snapshot.player_id,
        match_snapshot,
    )

    assert player_team == match_snapshot.players_a
    assert opponent_team == match_snapshot.players_b


def test_get_player_and_opponent_team_returns_team_b_for_player_b(
    player_b_snapshot,
    match_snapshot,
):
    player_team, opponent_team = _get_player_and_opponent_team(
        player_b_snapshot.player_id,
        match_snapshot,
    )

    assert player_team == match_snapshot.players_b
    assert opponent_team == match_snapshot.players_a


def test_get_player_and_opponent_team_returns_team_for_substitute(
    match_snapshot,
):
    substitute = match_snapshot.players_a[3]

    player_team, opponent_team = _get_player_and_opponent_team(
        substitute.player_id,
        match_snapshot,
    )

    assert player_team == match_snapshot.players_a
    assert opponent_team == match_snapshot.players_b


def test_get_player_and_opponent_team_raises_value_error_for_unknown_player(
    match_snapshot,
):
    with pytest.raises(ValueError):
        _get_player_and_opponent_team(
            999,
            match_snapshot,
        )


@pytest.mark.parametrize(
    "converter,pacss",
    [
        (control_range, 70),
        (max_move_speed, 60),
        (max_kick_force, 80),
    ],
)
def test_effective_physical_value_returns_full_value_without_penalty(
    converter,
    pacss,
):
    value = _effective_physical_value(
        pacss,
        0,
        converter,
    )

    assert isclose(
        value,
        converter(pacss),
    )


@pytest.mark.parametrize(
    "converter,pacss",
    [
        (control_range, 70),
        (max_move_speed, 60),
        (max_kick_force, 80),
    ],
)
def test_effective_physical_value_applies_collision_penalty(
    converter,
    pacss,
):
    value = _effective_physical_value(
        pacss,
        10,
        converter,
    )

    expected = converter(pacss) * COLLISION_PENALTY

    assert isclose(value, expected)


def test_build_behavior_context_for_team_a(
    player_a_snapshot,
    match_snapshot,
):
    context = build_behavior_context(
        match_snapshot,
        player_a_snapshot,
    )

    assert context.player == (
        player_a_snapshot.player_id,
        player_a_snapshot.position,
    )

    assert context.teammates == [
        (2, (6.0, 4.0)),
        (3, (7.0, 5.0)),
    ]

    assert context.opponents == [
        (7, (30.0, 10.0)),
        (8, (31.0, 8.0)),
        (9, (32.0, 6.0)),
    ]

    assert context.ball == (
        (20.0, 10.0),
        (1.0, 0.0),
    )

    assert context.my_team_score == 2
    assert context.opponent_score == 1
    assert context.side == Side.LEFT

    assert context.starting_position == (3.0, 3.0)
    assert context.tics_until_kick == 2


def test_build_behavior_context_for_team_b(
    player_b_snapshot,
    match_snapshot,
):
    context = build_behavior_context(
        match_snapshot,
        player_b_snapshot,
    )

    assert context.player == (
        player_b_snapshot.player_id,
        player_b_snapshot.position,
    )

    assert context.teammates == [
        (8, (31.0, 8.0)),
        (9, (32.0, 6.0)),
    ]

    assert context.opponents == [
        (1, (5.0, 4.0)),
        (2, (6.0, 4.0)),
        (3, (7.0, 5.0)),
    ]

    assert context.my_team_score == 1
    assert context.opponent_score == 2
    assert context.side == Side.RIGHT


def test_build_behavior_context_excludes_substitutes(
    player_a_snapshot,
    match_snapshot,
):
    context = build_behavior_context(
        match_snapshot,
        player_a_snapshot,
    )

    teammate_ids = {
        player_id
        for player_id, _ in context.teammates
    }

    opponent_ids = {
        player_id
        for player_id, _ in context.opponents
    }

    assert teammate_ids == {2, 3}
    assert opponent_ids == {7, 8, 9}

    assert 4 not in teammate_ids
    assert 5 not in teammate_ids
    assert 6 not in teammate_ids

    assert 10 not in opponent_ids
    assert 11 not in opponent_ids
    assert 12 not in opponent_ids


def test_build_behavior_context_calculates_remaining_time(
    player_a_snapshot,
    match_snapshot,
):
    context = build_behavior_context(
        match_snapshot,
        player_a_snapshot,
    )

    expected_time = (
        match_snapshot.duration_ticks
        - match_snapshot.current_tick
    ) * TIC_DURATION

    assert isclose(
        context.match_time_remaining,
        expected_time,
    )

    assert isclose(
        context.period_time_remaining,
        expected_time,
    )

    assert context.current_period == Period.FIRST_QUARTER


def test_build_behavior_context_uses_effective_physical_values_without_penalty(
    player_a_snapshot,
    match_snapshot,
):
    context = build_behavior_context(
        match_snapshot,
        player_a_snapshot,
    )

    assert isclose(
        context.control_range,
        control_range(player_a_snapshot.control),
    )

    assert isclose(
        context.max_move_speed,
        max_move_speed(player_a_snapshot.speed),
    )

    assert isclose(
        context.max_kick_force,
        max_kick_force(player_a_snapshot.power),
    )


def test_build_behavior_context_applies_collision_penalty(
    penalized_player_a_snapshot,
    match_snapshot,
):
    context = build_behavior_context(
        match_snapshot,
        penalized_player_a_snapshot,
    )

    assert isclose(
        context.control_range,
        control_range(
            penalized_player_a_snapshot.control
        ) * COLLISION_PENALTY,
    )

    assert isclose(
        context.max_move_speed,
        max_move_speed(
            penalized_player_a_snapshot.speed
        ) * COLLISION_PENALTY,
    )

    assert isclose(
        context.max_kick_force,
        max_kick_force(
            penalized_player_a_snapshot.power
        ) * COLLISION_PENALTY,
    )


def test_build_behavior_context_raises_if_player_is_not_on_field(
    substitute_player_snapshot,
    match_snapshot,
):
    with pytest.raises(ValueError):
        build_behavior_context(
            match_snapshot,
            substitute_player_snapshot,
        )


def test_build_behavior_context_raises_if_player_does_not_belong_to_match(
    player_a_snapshot,
    match_snapshot,
):
    unknown_player = type(player_a_snapshot)(
        **{
            **player_a_snapshot.__dict__,
            "player_id": 999,
        }
    )

    with pytest.raises(ValueError):
        build_behavior_context(
            match_snapshot,
            unknown_player,
        )

from dataclasses import replace


def test_build_behavior_context_raises_with_too_many_teammates_on_field(
    player_a_snapshot,
    match_snapshot,
):
    extra_starter = replace(
        match_snapshot.players_a[3],
        is_on_field=True,
        starting_position=(2.0, 2.0),
    )

    invalid_match = replace(
        match_snapshot,
        players_a=(
            *match_snapshot.players_a[:3],
            extra_starter,
            *match_snapshot.players_a[4:],
        ),
    )

    with pytest.raises(ValueError):
        build_behavior_context(
            invalid_match,
            player_a_snapshot,
        )


def test_build_behavior_context_raises_with_too_many_opponents_on_field(
    player_a_snapshot,
    match_snapshot,
):
    extra_starter = replace(
        match_snapshot.players_b[3],
        is_on_field=True,
        starting_position=(38.0, 2.0),
    )

    invalid_match = replace(
        match_snapshot,
        players_b=(
            *match_snapshot.players_b[:3],
            extra_starter,
            *match_snapshot.players_b[4:],
        ),
    )

    with pytest.raises(ValueError):
        build_behavior_context(
            invalid_match,
            player_a_snapshot,
        )
