"""
Build BehaviorContext instances from immutable match and player snapshots.

This module translates the global match state into the player-relative
state exposed through the Behavior API.
"""

from app.game.models.match import Match, MatchSnapshot
from app.game.models.match_participation import MatchParticipation
from app.game.models.player_in_match import PlayerInMatchSnapshot
from app.game.constants import TIC_DURATION
from app.game.context import BehaviorContext, CoachContext
from app.game.types import Period, CoachTrigger
from app.game.physics import (
    control_range,
    max_move_speed,
    max_kick_force,
    effective_physical_value
)


def build_behavior_context(
        match_snapshot: MatchSnapshot,
        player_snapshot: PlayerInMatchSnapshot,
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

    if player_team is match_snapshot.players_a:
        context_my_team_score = match_snapshot.score_a
        context_opponent_score = match_snapshot.score_b
        context_side = match_snapshot.side_a
    else:
        context_my_team_score = match_snapshot.score_b
        context_opponent_score = match_snapshot.score_a
        context_side = match_snapshot.side_b

    if player_snapshot.starting_position is None:
        raise ValueError("Player on field has no starting position")
    context_starting_position = player_snapshot.starting_position

    context_match_time_remaining = (
        match_snapshot.duration_ticks - match_snapshot.current_tick
    ) * TIC_DURATION

    # usw new info of the periods
    ticks_per_period = match_snapshot.duration_ticks // 4

    context_current_period = match_snapshot.current_period

    period_end_tick = (context_current_period.value * ticks_per_period)

    # max to solve possible inconsistences
    remaining_period_ticks = max(0, period_end_tick - match_snapshot.current_tick)

    context_period_time_remaining = (remaining_period_ticks * TIC_DURATION)

    context_control_range = effective_physical_value(
        player_snapshot.control,
        player_snapshot.collision_penalty_remaining,
        control_range,
    )

    context_tics_until_kick = player_snapshot.kick_cooldown_remaining

    context_max_move_speed = effective_physical_value(
        player_snapshot.speed,
        player_snapshot.collision_penalty_remaining,
        max_move_speed,
    )

    context_max_kick_force = effective_physical_value(
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
    match_snapshot: MatchSnapshot,
) -> tuple[
        tuple[PlayerInMatchSnapshot,...],
        tuple[PlayerInMatchSnapshot,...]
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


def build_coach_context(
        match: Match,
        participation: MatchParticipation,
        trigger: CoachTrigger,
) -> CoachContext:
    """
    Build the CoachContext for a club from the current match state.

    The context contains the match state from the club's perspective:
    its on-field players, the on-field opponents, score, field side,
    remaining time, ball state, the trigger that caused the execution and
    the behaviors the coach can assign.

    Args:
        match: Current match state.
        participation: Participation of the club whose coach is executed.
        trigger: Event that triggered the coach execution.

    Returns:
        CoachContext containing the state visible to the club's coach.

    Raises:
        ValueError: If the participation does not belong to the match.
    """
    if participation is match.participation_a:
        opponent_participation = match.participation_b
        context_side = match.side_a
    elif participation is match.participation_b:
        opponent_participation = match.participation_a
        context_side = match.side_b
    else:
        raise ValueError("Participation does not belong to this match")

    on_field_teammates = [
        player for player in participation.players if player.is_on_field
    ]

    context_teammates = [
        (player.player_id, player.position)
        for player in on_field_teammates
    ]

    context_opponents = [
        (player.player_id, player.position)
        for player in opponent_participation.players
        if player.is_on_field
    ]

    context_ball = (
        match.ball.position,
        match.ball.velocity,
    )

    context_match_time_remaining = (
        match.duration_ticks - match.current_tick
    ) * TIC_DURATION

    period_end_tick = match.current_period.value * (match.duration_ticks // 4)

    # max to solve possible inconsistences
    remaining_period_ticks = max(0, period_end_tick - match.current_tick)

    # inverse of the club catalog, to expose behavior names instead of ids
    behavior_names = {
        behavior_id: name
        for name, behavior_id in participation.available_behaviors.items()
    }

    context_current_behaviors = {
        player.player_id: behavior_names.get(player.current_behavior_id)
        for player in on_field_teammates
    }

    context_bench = [
        player.player_id
        for player in participation.players
        if not player.is_on_field
    ]

    context_can_substitute = (
        match.substitution_requests_open
        and participation.last_substitution_period != match.current_period
        and not participation.has_pending_manual_substitution()
    )

    return CoachContext(
        teammates=context_teammates,
        opponents=context_opponents,
        ball=context_ball,
        my_team_score=participation.goals,
        opponent_score=opponent_participation.goals,
        current_period=match.current_period,
        side=context_side,
        match_time_remaining=context_match_time_remaining,
        period_time_remaining=remaining_period_ticks * TIC_DURATION,
        trigger=trigger,
        available_behaviors=list(participation.available_behaviors),
        current_behaviors=context_current_behaviors,
        bench=context_bench,
        can_substitute=context_can_substitute,
    )
