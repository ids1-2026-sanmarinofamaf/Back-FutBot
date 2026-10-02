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
from app.game.types import Side
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


def test_resolve_kicks_returns_none_if_no_player_kicks(
    match_snapshot,
):
    engine = GameEngine()
    actions = _wait_actions_for_snapshot(match_snapshot)

    result = engine._resolve_kicks(
        match_snapshot,
        actions,
    )

    assert result is None


def test_resolve_kicks_returns_single_valid_kicker(
    match_snapshot,
):
    engine = GameEngine()

    player = replace(
        match_snapshot.players_a[0],
        position=(20.0, 10.0),
        kick_cooldown_remaining=0,
        forced_wait_remaining=0,
    )

    modified_snapshot = replace(
        match_snapshot,
        players_a=(
            player,
            *match_snapshot.players_a[1:],
        ),
    )

    actions = _wait_actions_for_snapshot(modified_snapshot)

    actions[player.player_id] = KickAction(
        kick_direction=(1.0, 0.0),
        kick_force_factor=1.0,
    )

    result = engine._resolve_kicks(
        modified_snapshot,
        actions,
    )

    assert result is not None
    assert result.contest.winner_id == player.player_id
    assert result.contest.loser_ids == ()
    assert result.action == actions[player.player_id]


def test_resolve_kicks_ignores_player_under_forced_wait(
    match_snapshot,
):
    engine = GameEngine()

    player = replace(
        match_snapshot.players_a[0],
        position=(20.0, 10.0),
        forced_wait_remaining=5,
        kick_cooldown_remaining=0,
    )

    modified_snapshot = replace(
        match_snapshot,
        players_a=(
            player,
            *match_snapshot.players_a[1:],
        ),
    )

    actions = _wait_actions_for_snapshot(modified_snapshot)

    actions[player.player_id] = KickAction(
        kick_direction=(1.0, 0.0),
        kick_force_factor=1.0,
    )

    result = engine._resolve_kicks(
        modified_snapshot,
        actions,
    )

    assert result is None


def test_resolve_kicks_ignores_player_with_kick_cooldown(
    match_snapshot,
):
    engine = GameEngine()

    player = replace(
        match_snapshot.players_a[0],
        position=(20.0, 10.0),
        forced_wait_remaining=0,
        kick_cooldown_remaining=3,
    )

    modified_snapshot = replace(
        match_snapshot,
        players_a=(
            player,
            *match_snapshot.players_a[1:],
        ),
    )

    actions = _wait_actions_for_snapshot(modified_snapshot)

    actions[player.player_id] = KickAction(
        kick_direction=(1.0, 0.0),
        kick_force_factor=1.0,
    )

    result = engine._resolve_kicks(
        modified_snapshot,
        actions,
    )

    assert result is None


def test_resolve_kicks_ignores_player_outside_control_range(
    match_snapshot,
):
    engine = GameEngine()

    player = replace(
        match_snapshot.players_a[0],
        position=(0.0, 0.0),
        forced_wait_remaining=0,
        kick_cooldown_remaining=0,
    )

    modified_snapshot = replace(
        match_snapshot,
        players_a=(
            player,
            *match_snapshot.players_a[1:],
        ),
    )

    actions = _wait_actions_for_snapshot(modified_snapshot)

    actions[player.player_id] = KickAction(
        kick_direction=(1.0, 0.0),
        kick_force_factor=1.0,
    )

    result = engine._resolve_kicks(
        modified_snapshot,
        actions,
    )

    assert result is None


def test_resolve_kicks_contest_prefers_higher_control(
    match_snapshot,
):
    engine = GameEngine()

    player_a = replace(
        match_snapshot.players_a[0],
        position=(20.0, 10.0),
        control=80,
        speed=60,
        strength=60,
        kick_cooldown_remaining=0,
        forced_wait_remaining=0,
    )

    player_b = replace(
        match_snapshot.players_b[0],
        position=(20.0, 10.0),
        control=60,
        speed=100,
        strength=100,
        kick_cooldown_remaining=0,
        forced_wait_remaining=0,
    )

    modified_snapshot = replace(
        match_snapshot,
        players_a=(
            player_a,
            *match_snapshot.players_a[1:],
        ),
        players_b=(
            player_b,
            *match_snapshot.players_b[1:],
        ),
    )

    actions = _wait_actions_for_snapshot(modified_snapshot)

    actions[player_a.player_id] = KickAction(
        kick_direction=(1.0, 0.0),
        kick_force_factor=1.0,
    )

    actions[player_b.player_id] = KickAction(
        kick_direction=(-1.0, 0.0),
        kick_force_factor=1.0,
    )

    result = engine._resolve_kicks(
        modified_snapshot,
        actions,
    )

    assert result is not None
    assert result.contest.winner_id == player_a.player_id
    assert result.contest.loser_ids == (player_b.player_id,)


def test_resolve_kicks_contest_prefers_higher_speed(
    match_snapshot,
):
    engine = GameEngine()

    player_a = replace(
        match_snapshot.players_a[0],
        position=(20.0, 10.0),
        control=60,
        speed=80,
        strength=60,
        kick_cooldown_remaining=0,
        forced_wait_remaining=0,
    )

    player_b = replace(
        match_snapshot.players_b[0],
        position=(20.0, 10.0),
        control=60,
        speed=60,
        strength=100,
        kick_cooldown_remaining=0,
        forced_wait_remaining=0,
    )

    modified_snapshot = replace(
        match_snapshot,
        players_a=(
            player_a,
            *match_snapshot.players_a[1:],
        ),
        players_b=(
            player_b,
            *match_snapshot.players_b[1:],
        ),
    )

    actions = _wait_actions_for_snapshot(modified_snapshot)

    actions[player_a.player_id] = KickAction(
        kick_direction=(1.0, 0.0),
        kick_force_factor=1.0,
    )

    actions[player_b.player_id] = KickAction(
        kick_direction=(-1.0, 0.0),
        kick_force_factor=1.0,
    )

    result = engine._resolve_kicks(
        modified_snapshot,
        actions,
    )

    assert result is not None
    assert result.contest.winner_id == player_a.player_id
    assert result.contest.loser_ids == (player_b.player_id,)


def test_resolve_kicks_contest_prefers_higher_strength(
    match_snapshot,
):
    engine = GameEngine()

    player_a = replace(
        match_snapshot.players_a[0],
        position=(20.0, 10.0),
        control=60,
        speed=60,
        strength=80,
        kick_cooldown_remaining=0,
        forced_wait_remaining=0,
    )

    player_b = replace(
        match_snapshot.players_b[0],
        position=(20.0, 10.0),
        control=60,
        speed=60,
        strength=60,
        kick_cooldown_remaining=0,
        forced_wait_remaining=0,
    )

    modified_snapshot = replace(
        match_snapshot,
        players_a=(
            player_a,
            *match_snapshot.players_a[1:],
        ),
        players_b=(
            player_b,
            *match_snapshot.players_b[1:],
        ),
    )

    actions = _wait_actions_for_snapshot(modified_snapshot)

    actions[player_a.player_id] = KickAction(
        kick_direction=(1.0, 0.0),
        kick_force_factor=1.0,
    )

    actions[player_b.player_id] = KickAction(
        kick_direction=(-1.0, 0.0),
        kick_force_factor=1.0,
    )

    result = engine._resolve_kicks(
        modified_snapshot,
        actions,
    )

    assert result is not None
    assert result.contest.winner_id == player_a.player_id
    assert result.contest.loser_ids == (player_b.player_id,)


def test_resolve_kicks_contest_prefers_last_conceding_side(
    match_snapshot,
):
    engine = GameEngine()

    player_a = replace(
        match_snapshot.players_a[0],
        position=(20.0, 10.0),
        control=60,
        speed=60,
        strength=60,
        kick_cooldown_remaining=0,
        forced_wait_remaining=0,
    )

    player_b = replace(
        match_snapshot.players_b[0],
        position=(20.0, 10.0),
        control=60,
        speed=60,
        strength=60,
        kick_cooldown_remaining=0,
        forced_wait_remaining=0,
    )

    modified_snapshot = replace(
        match_snapshot,
        players_a=(
            player_a,
            *match_snapshot.players_a[1:],
        ),
        players_b=(
            player_b,
            *match_snapshot.players_b[1:],
        ),
        last_conceding_side=Side.RIGHT,
    )

    actions = _wait_actions_for_snapshot(modified_snapshot)

    actions[player_a.player_id] = KickAction(
        kick_direction=(1.0, 0.0),
        kick_force_factor=1.0,
    )

    actions[player_b.player_id] = KickAction(
        kick_direction=(-1.0, 0.0),
        kick_force_factor=1.0,
    )

    result = engine._resolve_kicks(
        modified_snapshot,
        actions,
    )

    assert result is not None
    assert result.contest.winner_id == player_b.player_id
    assert result.contest.loser_ids == (player_a.player_id,)


def test_resolve_kicks_contest_prefers_lower_player_id(
    match_snapshot,
):
    engine = GameEngine()

    player_a = replace(
        match_snapshot.players_a[0],
        position=(20.0, 10.0),
        control=60,
        speed=60,
        strength=60,
        kick_cooldown_remaining=0,
        forced_wait_remaining=0,
    )

    player_b = replace(
        match_snapshot.players_b[0],
        position=(20.0, 10.0),
        control=60,
        speed=60,
        strength=60,
        kick_cooldown_remaining=0,
        forced_wait_remaining=0,
    )

    modified_snapshot = replace(
        match_snapshot,
        players_a=(
            player_a,
            *match_snapshot.players_a[1:],
        ),
        players_b=(
            player_b,
            *match_snapshot.players_b[1:],
        ),
        last_conceding_side=None,
    )

    actions = _wait_actions_for_snapshot(modified_snapshot)

    actions[player_a.player_id] = KickAction(
        kick_direction=(1.0, 0.0),
        kick_force_factor=1.0,
    )

    actions[player_b.player_id] = KickAction(
        kick_direction=(-1.0, 0.0),
        kick_force_factor=1.0,
    )

    result = engine._resolve_kicks(
        modified_snapshot,
        actions,
    )

    assert result is not None

    expected_winner_id = min(
        player_a.player_id,
        player_b.player_id,
    )

    expected_loser_id = max(
        player_a.player_id,
        player_b.player_id,
    )

    assert result.contest.winner_id == expected_winner_id
    assert result.contest.loser_ids == (expected_loser_id,)


def _wait_actions_for_snapshot(match_snapshot):
    return {
        player.player_id: WaitAction()
        for player in match_snapshot.players_a + match_snapshot.players_b
        if player.is_on_field
    }