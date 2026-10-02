import pytest
from dataclasses import replace

from app.game.constants import(
    FIELD_WIDTH,
    FIELD_HEIGHT,
    PLAYER_RADIUS,
    TIC_DURATION,
)
from app.game.engine import GameEngine
from app.game.models.actions import MoveAction, KickAction, WaitAction
from app.game.physics import max_move_speed


def test_validate_actions_accepts_one_action_per_on_field_player(
    match_snapshot,
):
    engine = GameEngine()

    actions = {
        player.player_id: WaitAction()
        for player in match_snapshot.players_a + match_snapshot.players_b
        if player.is_on_field
    }

    engine._validate_actions(
        match_snapshot,
        actions,
    )


def test_validate_actions_rejects_missing_action(
    match_snapshot,
):
    engine = GameEngine()

    actions = {
        player.player_id: WaitAction()
        for player in match_snapshot.players_a + match_snapshot.players_b
        if player.is_on_field
    }

    actions.pop(next(iter(actions)))

    with pytest.raises(ValueError):
        engine._validate_actions(
            match_snapshot,
            actions,
        )


def test_validate_actions_rejects_unexpected_player(
    match_snapshot,
):
    engine = GameEngine()

    actions = {
        player.player_id: WaitAction()
        for player in match_snapshot.players_a + match_snapshot.players_b
        if player.is_on_field
    }

    substitute = next(
        player
        for player in match_snapshot.players_a
        if not player.is_on_field
    )

    actions[substitute.player_id] = WaitAction()

    with pytest.raises(ValueError):
        engine._validate_actions(
            match_snapshot,
            actions,
        )


def test_validate_actions_rejects_invalid_action(
    match_snapshot,
):
    engine = GameEngine()

    actions = {
        player.player_id: WaitAction()
        for player in match_snapshot.players_a + match_snapshot.players_b
        if player.is_on_field
    }

    player_id = next(iter(actions))
    actions[player_id] = "invalid"

    with pytest.raises(ValueError):
        engine._validate_actions(
            match_snapshot,
            actions,
        )


from dataclasses import replace


def test_validate_actions_rejects_snapshot_without_six_on_field_players(
    match_snapshot,
):
    engine = GameEngine()

    player_out = replace(
        match_snapshot.players_a[0],
        is_on_field=False,
    )

    modified_snapshot = replace(
        match_snapshot,
        players_a=(
            player_out,
            *match_snapshot.players_a[1:],
        ),
    )

    actions = {
        player.player_id: WaitAction()
        for player in modified_snapshot.players_a + modified_snapshot.players_b
        if player.is_on_field
    }

    with pytest.raises(ValueError):
        engine._validate_actions(
            modified_snapshot,
            actions,
        )


def test_resolve_moves_keeps_position_for_wait_action(
    match_snapshot,
):
    engine = GameEngine()
    actions = _wait_actions_for_snapshot(match_snapshot)

    positions = engine._resolve_moves(
        match_snapshot,
        actions,
    )

    player = match_snapshot.players_a[0]

    assert positions[player.player_id] == player.position


def test_resolve_moves_keeps_position_for_kick_action(
    match_snapshot,
):
    engine = GameEngine()
    actions = _wait_actions_for_snapshot(match_snapshot)

    player = match_snapshot.players_a[0]

    actions[player.player_id] = KickAction(
        kick_direction=(1.0, 0.0),
        kick_force_factor=1.0,
    )

    positions = engine._resolve_moves(
        match_snapshot,
        actions,
    )

    assert positions[player.player_id] == player.position


def test_resolve_moves_updates_position_from_speed_and_factor(
    match_snapshot,
):
    engine = GameEngine()
    actions = _wait_actions_for_snapshot(match_snapshot)

    player = match_snapshot.players_a[0]

    actions[player.player_id] = MoveAction(
        move_direction=(1.0, 0.0),
        move_speed_factor=0.5,
    )

    positions = engine._resolve_moves(
        match_snapshot,
        actions,
    )

    expected_distance = (
        max_move_speed(player.speed)
        * 0.5
        * TIC_DURATION
    )

    assert positions[player.player_id] == (
        player.position[0] + expected_distance,
        player.position[1],
    )


def test_resolve_moves_with_zero_factor_keeps_position(
    match_snapshot,
):
    engine = GameEngine()
    actions = _wait_actions_for_snapshot(match_snapshot)

    player = match_snapshot.players_a[0]

    actions[player.player_id] = MoveAction(
        move_direction=(1.0, 0.0),
        move_speed_factor=0.0,
    )

    positions = engine._resolve_moves(
        match_snapshot,
        actions,
    )

    assert positions[player.player_id] == player.position


def test_resolve_moves_clamps_left_boundary(
    match_snapshot,
):
    engine = GameEngine()

    player = replace(
        match_snapshot.players_a[0],
        position=(PLAYER_RADIUS, 5.0),
    )

    modified_snapshot = replace(
        match_snapshot,
        players_a=(
            player,
            *match_snapshot.players_a[1:],
        ),
    )

    actions = _wait_actions_for_snapshot(modified_snapshot)

    actions[player.player_id] = MoveAction(
        move_direction=(-1.0, 0.0),
        move_speed_factor=1.0,
    )

    positions = engine._resolve_moves(
        modified_snapshot,
        actions,
    )

    assert positions[player.player_id][0] == PLAYER_RADIUS


def _wait_actions_for_snapshot(match_snapshot):
    return {
        player.player_id: WaitAction()
        for player in match_snapshot.players_a + match_snapshot.players_b
        if player.is_on_field
    }