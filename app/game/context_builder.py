"""
Build BehaviorContext instances from immutable match and player snapshots.

This module translates the global match state into the player-relative
state exposed through the Behavior API.
"""

from typing import Protocol, Callable

from app.game.constants import TIC_DURATION, COLLISION_PENALTY
from app.game.models.runtime_behavior import RuntimeBehavior
from app.game.context import BehaviorContext
from app.game.types import Position, Velocity, PlayerState, Side, Period
from app.game.physics import (
    control_range,
    max_move_speed,
    max_kick_force,
)


class PlayerInMatchSnapshotLike(Protocol):
    player_id: int

    position: Position
    velocity: Velocity
    starting_position: Position | None

    power: int
    agility: int
    control: int
    speed: int
    strength: int

    current_behavior: RuntimeBehavior | None
    is_on_field: bool

    kick_cooldown_remaining: int
    forced_wait_remaining: int
    collision_penalty_remaining: int


class BallSnapshotLike(Protocol):
    position: Position
    velocity: Velocity


class MatchSnapshotLike(Protocol):
    players_a: tuple[PlayerInMatchSnapshotLike, ...]
    players_b: tuple[PlayerInMatchSnapshotLike, ...]

    ball: BallSnapshotLike

    duration_ticks: int
    current_tick: int

    score_a: int
    score_b: int


def build_behavior_context(
        match_snapshot: MatchSnapshotLike,
        player_snapshot: PlayerInMatchSnapshotLike,
) -> BehaviorContext:
    """
    Build the BehaviorContext for a player from the current match snapshot.

    The context contains the match state from the player's perspective,
    including teammates, opponents, score, field side, remaining time,
    ball state, cooldowns, and effective physical capacities.

    Temporary collision penalties are applied to CONTROL, SPEED, and POWER
    when calculating the effective values exposed to the behavior.

    Args:
        match_snapshot: Immutable snapshot of the current match state.
        player_snapshot: Snapshot of the player whose context is being built.

    Returns:
        BehaviorContext containing the state visible to the player's behavior.

    Raises:
        ValueError: If the player is not on the field, does not belong to
        either team, or the match contains an invalid number of players
        on the field.
    """
    if not player_snapshot.is_on_field:
        raise ValueError("Player is not on field")

    context_player = (player_snapshot.player_id, player_snapshot.position)

    player_team, opponent_team = _get_player_and_opponent_team(
        player_snapshot.player_id,
        match_snapshot,
    )

    context_teammates = [
        (player.player_id, player.position)
        for player in player_team
        if (player.player_id != player_snapshot.player_id 
            and player.is_on_field
        )
    ]
    if len(context_teammates) != 2:
        raise ValueError("Invalid number of teammates on field")

    context_opponents = [
        (player.player_id, player.position)
        for player in opponent_team
        if player.is_on_field
    ]
    if len(context_opponents) != 3:
        raise ValueError("Invalid number of opponents on field")

    context_ball = (
        match_snapshot.ball.position,
        match_snapshot.ball.velocity
    )

    if player_team == match_snapshot.players_a:
        context_my_team_score = match_snapshot.score_a
        context_opponent_score = match_snapshot.score_b
        context_side = Side.LEFT
    else:
        context_my_team_score = match_snapshot.score_b
        context_opponent_score = match_snapshot.score_a
        context_side = Side.RIGHT

    if player_snapshot.starting_position is None:
        raise ValueError("Player on field has no starting position")
    context_starting_position = player_snapshot.starting_position

    context_match_time_remaining = (
        match_snapshot.duration_ticks - match_snapshot.current_tick
    ) * TIC_DURATION

    # For second sprint it's ok
    context_current_period = Period.FIRST_QUARTER
    context_period_time_remaining = context_match_time_remaining

    context_control_range = _effective_physical_value(
        player_snapshot.control,
        player_snapshot.collision_penalty_remaining,
        control_range,
    )

    context_tics_until_kick = player_snapshot.kick_cooldown_remaining

    context_max_move_speed = _effective_physical_value(
        player_snapshot.speed,
        player_snapshot.collision_penalty_remaining,
        max_move_speed,
    )

    context_max_kick_force = _effective_physical_value(
        player_snapshot.power,
        player_snapshot.collision_penalty_remaining,
        max_kick_force,
    )

    return BehaviorContext(
        player=context_player,
        teammates=context_teammates,
        opponents=context_opponents,
        ball=context_ball,
        my_team_score=context_my_team_score,
        opponent_score=context_opponent_score,
        starting_position=context_starting_position,
        current_period=context_current_period,
        side=context_side,
        match_time_remaining=context_match_time_remaining,
        period_time_remaining=context_period_time_remaining,
        control_range=context_control_range,
        tics_until_kick=context_tics_until_kick,
        max_move_speed=context_max_move_speed,
        max_kick_force=context_max_kick_force,
    )


def _get_player_and_opponent_team(
    player_id: int,
    match_snapshot: MatchSnapshotLike,
) -> tuple[
        tuple[PlayerInMatchSnapshotLike,...],
        tuple[PlayerInMatchSnapshotLike,...]
    ]:
    """
    Return the player's team and the opposing team.

    Args:
        player_id: Identifier of the player.
        match_snapshot: Current immutable match state.

    Returns:
        A tuple containing the player's team first and the opponent team second.

    Raises:
        ValueError: If the player does not belong to either team.
    """
    team_a = match_snapshot.players_a
    team_b = match_snapshot.players_b

    if any(player.player_id == player_id for player in team_a):
        player_team = team_a
        opponent_team = team_b

    elif any(player.player_id == player_id for player in team_b):
        player_team = team_b
        opponent_team = team_a

    else:
        raise ValueError(f"Player {player_id} does not belong to this match")

    return player_team, opponent_team


def _effective_physical_value(
    pacss: int,
    collision_penalty_remaining: int,
    converter: Callable[[int], float],
) -> float:
    max_value = converter(pacss)

    return(
        max_value * COLLISION_PENALTY
        if collision_penalty_remaining > 0
        else max_value
    )