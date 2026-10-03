import pytest
from dataclasses import replace

from app.game.constants import(
    FIELD_WIDTH,
    FIELD_HEIGHT,
    PLAYER_RADIUS,
    TIC_DURATION,
    COLLISION_FORCED_WAIT_TICS,
    COLLISION_PENALTY_TICS,
    BALL_RADIUS,
    WALL_BOUNCE_SPEED_FACTOR,
)
from app.game.engine import GameEngine
from app.game.models.actions import MoveAction, KickAction, WaitAction
from app.game.models.match import Match
from app.game.models.ball import Ball
from app.game.models.match_participation import MatchParticipation
from app.game.models.player_in_match import PlayerInMatch
from app.game.types import Side
from app.game.physics import(
    max_move_speed,
    collision_time,
    position_at_time,
    calculate_kick_velocity,
    calculate_ball_state_after,
)


def _make_player(
    player_id: int,
    is_on_field: bool,
) -> PlayerInMatch:
    return PlayerInMatch(
        player_id=player_id,
        position=(0.0, 0.0),
        velocity=(0.0, 0.0),
        starting_position=(0.0, 0.0) if is_on_field else None,
        power=60,
        agility=60,
        control=60,
        speed=60,
        strength=60,
        current_behavior_id=1 if is_on_field else None,
        is_on_field=is_on_field,
    )


def _make_participation(
    start_id: int,
) -> MatchParticipation:
    return MatchParticipation(
        club_id=start_id,
        roster_id=start_id,
        players=[
            _make_player(start_id, True),
            _make_player(start_id + 1, True),
            _make_player(start_id + 2, True),
            _make_player(start_id + 3, False),
            _make_player(start_id + 4, False),
            _make_player(start_id + 5, False),
        ],
    )


@pytest.fixture
def match():
    return Match(
        match_id=1,
        participation_a=_make_participation(1),
        participation_b=_make_participation(7),
        ball=Ball(
            position=(20.0, 10.0),
            velocity=(0.0, 0.0),
        ),
        duration_ticks=1200,
    )


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


def test_resolve_player_collisions_without_collision(
    match_snapshot,
):
    engine = GameEngine()

    proposed_positions = _proposed_positions_from_snapshot(
        match_snapshot
    )

    final_positions, loser_ids = (
        engine._resolve_player_collisions(
            match_snapshot,
            proposed_positions,
        )
    )

    assert final_positions == proposed_positions
    assert loser_ids == set()


def test_resolve_player_collisions_stops_loser_at_collision_point(
    match_snapshot,
):
    engine = GameEngine()

    player_a = replace(
        match_snapshot.players_a[0],
        position=(10.0, 10.0),
        strength=100,
    )

    player_b = replace(
        match_snapshot.players_b[0],
        position=(12.0, 10.0),
        strength=20,
    )

    snapshot = replace(
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

    proposed_positions = _proposed_positions_from_snapshot(snapshot)

    proposed_positions[player_a.player_id] = (12.0, 10.0)
    proposed_positions[player_b.player_id] = (10.0, 10.0)

    final_positions, loser_ids = (
        engine._resolve_player_collisions(
            snapshot,
            proposed_positions,
        )
    )

    assert loser_ids == {player_b.player_id}

    # Winner completes its movement.
    assert final_positions[player_a.player_id] == (12.0, 10.0)

    # Loser must stop before reaching its proposed position.
    assert final_positions[player_b.player_id] != (10.0, 10.0)


def test_resolve_player_collisions_uses_collision_position(
    match_snapshot,
):
    engine = GameEngine()

    player_a = replace(
        match_snapshot.players_a[0],
        position=(10.0, 10.0),
        strength=100,
    )

    player_b = replace(
        match_snapshot.players_b[0],
        position=(12.0, 10.0),
        strength=20,
    )

    snapshot = replace(
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

    proposed_positions = _proposed_positions_from_snapshot(snapshot)

    proposed_positions[player_a.player_id] = (12.0, 10.0)
    proposed_positions[player_b.player_id] = (10.0, 10.0)

    collision_t = collision_time(
        player_a.position,
        proposed_positions[player_a.player_id],
        PLAYER_RADIUS,
        player_b.position,
        proposed_positions[player_b.player_id],
        PLAYER_RADIUS,
    )

    assert collision_t is not None

    expected_loser_position = position_at_time(
        player_b.position,
        proposed_positions[player_b.player_id],
        collision_t,
    )

    final_positions, _ = engine._resolve_player_collisions(
        snapshot,
        proposed_positions,
    )

    assert final_positions[player_b.player_id] == pytest.approx(
        expected_loser_position
    )


def test_collision_contest_prefers_higher_strength(
    match_snapshot,
):
    engine = GameEngine()

    player_a = replace(
        match_snapshot.players_a[0],
        strength=80,
        power=20,
        speed=20,
    )

    player_b = replace(
        match_snapshot.players_b[0],
        strength=60,
        power=100,
        speed=100,
    )

    result = engine._resolve_collision_contest(
        [player_a, player_b]
    )

    assert result.winner_id == player_a.player_id
    assert result.loser_ids == (player_b.player_id,)


def test_collision_contest_prefers_higher_power(
    match_snapshot,
):
    engine = GameEngine()

    player_a = replace(
        match_snapshot.players_a[0],
        strength=60,
        power=80,
        speed=20,
    )

    player_b = replace(
        match_snapshot.players_b[0],
        strength=60,
        power=60,
        speed=100,
    )

    result = engine._resolve_collision_contest(
        [player_a, player_b]
    )

    assert result.winner_id == player_a.player_id


def test_collision_contest_prefers_higher_speed(
    match_snapshot,
):
    engine = GameEngine()

    player_a = replace(
        match_snapshot.players_a[0],
        strength=60,
        power=60,
        speed=80,
    )

    player_b = replace(
        match_snapshot.players_b[0],
        strength=60,
        power=60,
        speed=60,
    )

    result = engine._resolve_collision_contest(
        [player_a, player_b]
    )

    assert result.winner_id == player_a.player_id


def test_collision_contest_prefers_lower_player_id(
    match_snapshot,
):
    engine = GameEngine()

    player_a = replace(
        match_snapshot.players_a[0],
        strength=60,
        power=60,
        speed=60,
    )

    player_b = replace(
        match_snapshot.players_b[0],
        strength=60,
        power=60,
        speed=60,
    )

    result = engine._resolve_collision_contest(
        [player_a, player_b]
    )

    assert result.winner_id == min(
        player_a.player_id,
        player_b.player_id,
    )


def test_collision_contest_supports_multiple_players(
    match_snapshot,
):
    engine = GameEngine()

    player_a = replace(
        match_snapshot.players_a[0],
        strength=60,
    )

    player_b = replace(
        match_snapshot.players_a[1],
        strength=80,
    )

    player_c = replace(
        match_snapshot.players_b[0],
        strength=40,
    )

    result = engine._resolve_collision_contest(
        [player_a, player_b, player_c]
    )

    assert result.winner_id == player_b.player_id
    assert set(result.loser_ids) == {
        player_a.player_id,
        player_c.player_id,
    }


def test_group_collision_events_merges_connected_collisions():
    engine = GameEngine()

    collisions = [
        (0.5, 1, 2),
        (0.5, 3, 4),
        (0.5, 2, 3),
    ]

    events = engine._group_collision_events(collisions)

    assert len(events) == 1

    time, player_ids = events[0]

    assert time == pytest.approx(0.5)
    assert player_ids == {1, 2, 3, 4}


def test_group_collision_events_keeps_different_times_separate():
    engine = GameEngine()

    collisions = [
        (0.25, 1, 2),
        (0.75, 2, 3),
    ]

    events = engine._group_collision_events(collisions)

    assert len(events) == 2


def test_apply_collision_effects_penalizes_only_losers():
    engine = GameEngine()

    participation_a = _make_participation(1)
    participation_b = _make_participation(7)

    match = Match(
        match_id=1,
        participation_a=participation_a,
        participation_b=participation_b,
        ball=Ball(
            position=(20.0, 10.0),
            velocity=(0.0, 0.0),
        ),
        duration_ticks=1200,
    )

    loser_a = participation_a.players[0]
    loser_b = participation_b.players[1]

    loser_ids = {
        loser_a.player_id,
        loser_b.player_id,
    }

    engine._apply_collision_effects(
        match,
        loser_ids,
    )

    assert loser_a.forced_wait_remaining == (
        COLLISION_FORCED_WAIT_TICS + 1
    )
    assert loser_a.collision_penalty_remaining == (
        COLLISION_PENALTY_TICS + 1
    )

    assert loser_b.forced_wait_remaining == (
        COLLISION_FORCED_WAIT_TICS + 1
    )
    assert loser_b.collision_penalty_remaining == (
        COLLISION_PENALTY_TICS + 1
    )

    for participation in (
        match.participation_a,
        match.participation_b,
    ):
        for player in participation.players:
            if player.player_id in loser_ids:
                continue

            assert player.forced_wait_remaining == 0
            assert player.collision_penalty_remaining == 0


def test_apply_collision_effects_does_nothing_without_losers():
    engine = GameEngine()

    match = Match(
        match_id=1,
        participation_a=_make_participation(1),
        participation_b=_make_participation(7),
        ball=Ball(
            position=(20.0, 10.0),
            velocity=(0.0, 0.0),
        ),
        duration_ticks=1200,
    )

    engine._apply_collision_effects(
        match,
        set(),
    )

    for participation in (
        match.participation_a,
        match.participation_b,
    ):
        for player in participation.players:
            assert player.forced_wait_remaining == 0
            assert player.collision_penalty_remaining == 0


def test_apply_collision_effects_ignores_substitutes(
    match,
):
    engine = GameEngine()

    substitute = match.participation_a.players[3]

    engine._apply_collision_effects(
        match,
        {substitute.player_id},
    )

    assert substitute.forced_wait_remaining == 0
    assert substitute.collision_penalty_remaining == 0


def test_apply_player_positions_updates_on_field_players(
    match,
):
    engine = GameEngine()

    player_a = match.participation_a.players[0]
    player_b = match.participation_b.players[1]

    final_positions = {
        player_a.player_id: (10.0, 5.0),
        player_b.player_id: (30.0, 15.0),
    }

    engine._apply_player_positions(
        match,
        final_positions,
    )

    assert player_a.position == (10.0, 5.0)
    assert player_b.position == (30.0, 15.0)


def test_apply_player_positions_keeps_unlisted_players_unchanged(
    match,
):
    engine = GameEngine()

    updated_player = match.participation_a.players[0]
    unchanged_player = match.participation_a.players[1]

    original_position = unchanged_player.position

    engine._apply_player_positions(
        match,
        {
            updated_player.player_id: (10.0, 5.0),
        },
    )

    assert updated_player.position == (10.0, 5.0)
    assert unchanged_player.position == original_position


def _wait_actions_for_snapshot(match_snapshot):
    return {
        player.player_id: WaitAction()
        for player in match_snapshot.players_a + match_snapshot.players_b
        if player.is_on_field
    }


def test_apply_player_positions_ignores_substitutes(
    match,
):
    engine = GameEngine()

    substitute = match.participation_a.players[3]
    original_position = substitute.position

    engine._apply_player_positions(
        match,
        {
            substitute.player_id: (20.0, 10.0),
        },
    )

    assert substitute.position == original_position


def _proposed_positions_from_snapshot(snapshot):
    return {
        player.player_id: player.position
        for player in snapshot.players_a + snapshot.players_b
        if player.is_on_field
    }


def test_ball_state_after_kick_changes_velocity():
    engine = GameEngine()

    ball_state = (
        (20.0, 10.0),
        (0.0, 0.0),
    )

    action = KickAction(
        kick_direction=(1.0, 0.0),
        kick_force_factor=0.5,
    )

    result = engine._ball_state_after_kick(
        ball_state,
        action,
        effective_power=20.0,
    )

    position, velocity = result

    assert position == (20.0, 10.0)
    assert velocity == pytest.approx(
        calculate_kick_velocity(
            (0.0, 0.0),
            (1.0, 0.0),
            10.0,
        )
    )


def test_ball_state_after_kick_uses_current_ball_velocity():
    engine = GameEngine()

    ball_state = (
        (20.0, 10.0),
        (5.0, 0.0),
    )

    action = KickAction(
        kick_direction=(1.0, 0.0),
        kick_force_factor=1.0,
    )

    result = engine._ball_state_after_kick(
        ball_state,
        action,
        effective_power=20.0,
    )

    _, velocity = result

    assert velocity == pytest.approx(
        calculate_kick_velocity(
            (5.0, 0.0),
            (1.0, 0.0),
            20.0,
        )
    )


def test_first_ball_boundary_event_returns_none_when_no_boundary_is_reached():
    engine = GameEngine()

    result = engine._first_ball_boundary_event(
        start=(20.0, 10.0),
        end=(21.0, 10.0),
    )

    assert result is None


def test_first_ball_boundary_event_detects_left_wall():
    engine = GameEngine()

    result = engine._first_ball_boundary_event(
        start=(1.0, 5.0),
        end=(-1.0, 5.0),
    )

    assert result is not None

    time, event = result

    assert event == "left"
    assert 0.0 <= time <= 1.0


def test_first_ball_boundary_event_detects_right_wall():
    engine = GameEngine()

    result = engine._first_ball_boundary_event(
        start=(39.0, 5.0),
        end=(41.0, 5.0),
    )

    assert result is not None

    _, event = result

    assert event == "right"


def test_first_ball_boundary_event_detects_top_wall():
    engine = GameEngine()

    result = engine._first_ball_boundary_event(
        start=(20.0, 1.0),
        end=(20.0, -1.0),
    )

    assert result is not None
    assert result[1] == "top"


def test_first_ball_boundary_event_detects_bottom_wall():
    engine = GameEngine()

    result = engine._first_ball_boundary_event(
        start=(20.0, 19.0),
        end=(20.0, 21.0),
    )

    assert result is not None
    assert result[1] == "bottom"


def test_first_ball_boundary_event_detects_left_goal():
    engine = GameEngine()

    result = engine._first_ball_boundary_event(
        start=(1.0, 10.0),
        end=(-1.0, 10.0),
    )

    assert result is not None
    assert result[1] == "goal_left"


def test_first_ball_boundary_event_detects_right_goal():
    engine = GameEngine()

    result = engine._first_ball_boundary_event(
        start=(39.0, 10.0),
        end=(41.0, 10.0),
    )

    assert result is not None
    assert result[1] == "goal_right"


def test_first_ball_boundary_event_returns_earliest_event():
    engine = GameEngine()

    result = engine._first_ball_boundary_event(
        start=(39.0, 1.0),
        end=(41.0, -3.0),
    )

    assert result is not None

    _, event = result

    assert event == "top"

def test_first_ball_boundary_event_calculates_collision_time():
    engine = GameEngine()

    result = engine._first_ball_boundary_event(
        start=(1.0, 5.0),
        end=(-1.0, 5.0),
    )

    assert result is not None

    time, event = result

    expected_time = (
        BALL_RADIUS - 1.0
    ) / (-2.0)

    assert event == "left"
    assert time == pytest.approx(expected_time)


def test_bounce_ball_velocity_on_vertical_wall():
    engine = GameEngine()

    result = engine._bounce_ball_velocity(
        velocity=(10.0, 4.0),
        boundary="right",
    )

    assert result == pytest.approx(
        (
            -10.0 * WALL_BOUNCE_SPEED_FACTOR,
            4.0 * WALL_BOUNCE_SPEED_FACTOR,
        )
    )


def test_bounce_ball_velocity_on_horizontal_wall():
    engine = GameEngine()

    result = engine._bounce_ball_velocity(
        velocity=(10.0, -4.0),
        boundary="top",
    )

    assert result == pytest.approx(
        (
            10.0 * WALL_BOUNCE_SPEED_FACTOR,
            4.0 * WALL_BOUNCE_SPEED_FACTOR,
        )
    )

def test_resolve_ball_movement_without_boundary():
    engine = GameEngine()

    ball_state = (
        (20.0, 10.0),
        (5.0, 0.0),
    )

    result = engine._resolve_ball_movement(ball_state)

    expected = calculate_ball_state_after(
        ball_state,
        TIC_DURATION,
    )

    assert result[0] == pytest.approx(expected[0])
    assert result[1] == pytest.approx(expected[1])


def test_resolve_ball_movement_bounces_on_right_wall():
    engine = GameEngine()

    ball_state = (
        (FIELD_WIDTH - BALL_RADIUS - 0.2, 5.0),
        (10.0, 0.0),
    )

    position, velocity = engine._resolve_ball_movement(
        ball_state
    )

    assert position[0] < FIELD_WIDTH - BALL_RADIUS
    assert velocity[0] < 0.0


def test_resolve_ball_movement_bounces_on_top_wall():
    engine = GameEngine()

    ball_state = (
        (20.0, BALL_RADIUS + 0.2),
        (0.0, -10.0),
    )

    position, velocity = engine._resolve_ball_movement(
        ball_state
    )

    assert position[1] > BALL_RADIUS
    assert velocity[1] > 0.0


def test_resolve_ball_movement_stops_at_right_goal_line():
    engine = GameEngine()

    ball_state = (
        (FIELD_WIDTH - 0.5, FIELD_HEIGHT / 2),
        (10.0, 0.0),
    )

    position, velocity = engine._resolve_ball_movement(
        ball_state
    )

    assert position[0] == pytest.approx(FIELD_WIDTH)
    assert engine._is_inside_goal_opening(position[1])
    assert velocity[0] > 0.0


def test_resolve_ball_movement_stops_at_left_goal_line():
    engine = GameEngine()

    ball_state = (
        (0.5, FIELD_HEIGHT / 2),
        (-10.0, 0.0),
    )

    position, velocity = engine._resolve_ball_movement(
        ball_state
    )

    assert position[0] == pytest.approx(0.0)
    assert engine._is_inside_goal_opening(position[1])
    assert velocity[0] < 0.0