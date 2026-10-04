from dataclasses import dataclass
from math import isclose

from app.game.models.match import Match, MatchSnapshot
from app.game.models.player_in_match import PlayerInMatchSnapshot
from app.game.models.actions import MoveAction, KickAction, WaitAction
from app.game.types import Position, Side, BallState
from app.game.constants import(
    TIC_DURATION,
    FIELD_HEIGHT,
    FIELD_WIDTH,
    GOAL_WIDTH,
    PLAYER_RADIUS, 
    COLLISION_FORCED_WAIT_TICS,
    COLLISION_PENALTY_TICS,
    BALL_RADIUS,
    WALL_BOUNCE_SPEED_FACTOR,
    GOAL_RESTART_WAIT_TICS,
    FIELD_CENTER,
    RESTART_BALL_SPEED,
    )
from app.game.physics import(
    max_move_speed,
    control_range,
    max_kick_force,
    effective_physical_value,
    distance,
    collision_time,
    position_at_time,
    calculate_kick_velocity,
    calculate_ball_state_after,
    direction_to,
    kick_cooldown_tics,
)


Action = MoveAction | KickAction | WaitAction


@dataclass(frozen=True)
class ContestResolution:
    winner_id: int
    loser_ids: tuple[int, ...]


@dataclass(frozen=True)
class KickResolution:
    contest: ContestResolution
    action: KickAction


class GameEngine:
    """
    Resolve one simulation tic and update the mutable match state.
    """
    def step(
            self,
            match: Match,
            snapshot: MatchSnapshot,
            actions: dict[int, Action]

    ) -> None:
        """
        Resolve all actions and game interactions for one simulation tic.

        All decisions are calculated from the same immutable match snapshot.
        The mutable match is updated only with the final results of the tic.

        Args:
            match: Mutable match state to update.
            snapshot: Immutable state at the beginning of the tic.
            actions: One action for each on-field player.
        """
        self._validate_actions(snapshot, actions)

        # Initial / period restart.
        if snapshot.current_tick == 0:
            self._restitute_ball(
                match,
                Side.LEFT,
            )
            return

        kick_result = self._resolve_kicks(
            snapshot,
            actions,
        )

        proposed_positions = self._resolve_moves(
            snapshot,
            actions,
        )

        final_positions, collision_loser_ids = (
            self._resolve_player_collisions(
                snapshot,
                proposed_positions,
            )
        )

        self._apply_collision_effects(
            match,
            collision_loser_ids,
        )

        self._apply_player_positions(
            match,
            final_positions,
        )

        self._update_ball(
            match,
            snapshot,
            kick_result,
            final_positions,
        )

        conceding_side = self._detect_goal(match)

        if conceding_side is not None:
            self._handle_goal(
                match,
                conceding_side,
            )

        restart_ending = self._is_goal_restart_ending(match)

        self._update_timers(match)

        if restart_ending:
            self._restitute_ball(
                match,
                match.last_conceding_side,
            )



    def _validate_actions(
        self,
        snapshot: MatchSnapshot,
        actions: dict[int, Action],
    ) -> None:
        """
        Validate that the engine received exactly one valid action
        for each of the six on-field players.

        Raises:
            ValueError: If the actions do not match the six on-field players
            or if any action has an invalid type.
        """
        players = self._get_on_field_players(snapshot)

        if len(players) != 6:
            raise ValueError(
                "A match must have exactly 6 on-field players"
            )

        if set(actions.keys()) != set(players.keys()):
            raise ValueError(
                "Actions must match exactly the on-field players"
            )

        if not all(
            isinstance(action, (MoveAction, KickAction, WaitAction))
            for action in actions.values()
        ):
            raise ValueError("Invalid player action")


    def _resolve_kicks(
        self,
        snapshot: MatchSnapshot,
        actions: dict[int, Action],
    ) -> KickResolution | None:
        players = self._get_on_field_players(snapshot)

        valid_kickers = []

        for player_id, player in players.items():
            action = actions[player_id]

            if not isinstance(action, KickAction):
                continue

            if not self._can_attempt_kick(
                player,
                snapshot.ball.position,
            ):
                continue

            valid_kickers.append(player)

        if not valid_kickers:
            return None

        winner = max(
            valid_kickers,
            key=lambda player: self._kick_contest_key(
                snapshot,
                player,
            ),
        )

        loser_ids = tuple(
            player.player_id
            for player in valid_kickers
            if player.player_id != winner.player_id
        )

        return KickResolution(
            contest=ContestResolution(
                winner_id=winner.player_id,
                loser_ids=loser_ids,
            ),
            action=actions[winner.player_id],
        )


    def _resolve_moves(
        self,
        snapshot: MatchSnapshot,
        actions: dict[int, Action],
    ) -> dict[int, Position]:
        players = self._get_on_field_players(snapshot)

        proposed_positions = {
            player_id: player.position
            for player_id, player in players.items()
        }

        for player_id, player in players.items():
            action = actions[player_id]

            if player.forced_wait_remaining > 0:
                continue

            if not isinstance(action, MoveAction):
                continue

            move_speed = effective_physical_value(
                player.speed,
                player.collision_penalty_remaining,
                max_move_speed,
            )

            distance = (
                move_speed
                * action.move_speed_factor
                * TIC_DURATION
            )

            proposed_x = (
                player.position[0]
                + action.move_direction[0] * distance
            )

            proposed_y = (
                player.position[1]
                + action.move_direction[1] * distance
            )

            proposed_positions[player_id] = self._clamp_player_position(
                (proposed_x, proposed_y)
            )

        return proposed_positions


    def _resolve_player_collisions(
        self,
        snapshot: MatchSnapshot,
        proposed_positions: dict[int, Position],
    ) -> tuple[
        dict[int, Position],
        set[int],
    ]:
        players = self._get_on_field_players(snapshot)

        final_positions = proposed_positions.copy()
        collision_loser_ids: set[int] = set()

        detected_collisions: list[tuple[float, int, int]] = []
        player_ids = list(players.keys())

        # Detect every pairwise collision during the tic.
        for i in range(len(player_ids)):
            for j in range(i + 1, len(player_ids)):
                player_a = players[player_ids[i]]
                player_b = players[player_ids[j]]

                time = collision_time(
                    player_a.position,
                    proposed_positions[player_a.player_id],
                    PLAYER_RADIUS,
                    player_b.position,
                    proposed_positions[player_b.player_id],
                    PLAYER_RADIUS,
                )

                if time is None:
                    continue

                detected_collisions.append(
                    (
                        time,
                        player_a.player_id,
                        player_b.player_id,
                    )
                )

        # Earlier collision events must be resolved first.
        detected_collisions.sort(
            key=lambda collision: collision[0]
        )

        collision_events = self._group_collision_events(
            detected_collisions
        )

        for time, involved_ids in collision_events:
            involved_players = [
                players[player_id]
                for player_id in involved_ids
            ]

            contest = self._resolve_collision_contest(
                involved_players
            )

            for loser_id in contest.loser_ids:
                loser = players[loser_id]

                final_positions[loser_id] = position_at_time(
                    loser.position,
                    proposed_positions[loser_id],
                    time,
                )

                collision_loser_ids.add(loser_id)

        return final_positions, collision_loser_ids


    def _apply_collision_effects(
        self,
        match: Match,
        loser_ids: set[int],
    ) -> None:
        for participation in (
            match.participation_a, 
            match.participation_b,
        ):
            for player in participation.players:
                if not player.is_on_field:
                    continue

                if player.player_id not in loser_ids:
                    continue

                player.forced_wait_remaining = (
                    COLLISION_FORCED_WAIT_TICS + 1
                )

                player.collision_penalty_remaining = (
                    COLLISION_PENALTY_TICS + 1
                )


    def _apply_player_positions(
        self,
        match: Match,
        final_positions: dict[int, Position],
    ) -> None:
        for participation in (
            match.participation_a,
            match.participation_b,
        ):
            for player in participation.players:
                if not player.is_on_field:
                    continue

                if player.player_id not in final_positions:
                    continue

                player.position = final_positions[player.player_id]


    def _update_ball(
        self,
        match: Match,
        snapshot: MatchSnapshot,
        kick_result: KickResolution | None,
        final_positions: dict[int, Position],
    ) -> None:
        ball_state: BallState = (
            snapshot.ball.position,
            snapshot.ball.velocity,
        )

        if kick_result is not None:
            players = self._get_on_field_players(snapshot)

            winner = players[
                kick_result.contest.winner_id
            ]

            effective_power = effective_physical_value(
                winner.power,
                winner.collision_penalty_remaining,
                max_kick_force,
            )

            ball_state = self._ball_state_after_kick(
                ball_state,
                kick_result.action,
                effective_power,
            )

            for participation in (
                match.participation_a,
                match.participation_b,
            ):
                for player in participation.players:
                    if player.player_id == winner.player_id:
                        player.kick_cooldown_remaining = (
                            kick_cooldown_tics(winner.agility) + 1
                        )
                        break

        ball_state = self._resolve_ball_movement(
            ball_state,
        )

        match.ball.position = ball_state[0]
        match.ball.velocity = ball_state[1]


    def _detect_goal(
        self,
        match: Match,
    ) -> Side | None:
        x, y = match.ball.position

        if not self._is_inside_goal_opening(y):
            return None

        if x <= 0.0:
            return Side.LEFT

        if x >= FIELD_WIDTH:
            return Side.RIGHT

        return None


    def _handle_goal(
        self,
        match: Match,
        conceding_side: Side,
    ) -> None:
        # Score for the opposite side.
        if conceding_side == Side.LEFT:
            match.participation_b.goals += 1
        else:
            match.participation_a.goals += 1

        match.last_conceding_side = conceding_side

        # Reset ball to the center.
        match.ball.position = FIELD_CENTER
        match.ball.velocity = (0.0, 0.0)

        # Reset on-field players.
        for participation in (
            match.participation_a,
            match.participation_b,
        ):
            for player in participation.players:
                if not player.is_on_field:
                    continue

                if player.starting_position is not None:
                    player.position = player.starting_position

                player.kick_cooldown_remaining = 0
                player.collision_penalty_remaining = 0

                player.forced_wait_remaining = (
                    GOAL_RESTART_WAIT_TICS + 1
                )


    def _update_timers(
        self,
        match: Match,
    ) -> None:
        for participation in (
            match.participation_a,
            match.participation_b,
        ):
            for player in participation.players:
                if not player.is_on_field:
                    continue

                if player.kick_cooldown_remaining > 0:
                    player.kick_cooldown_remaining -= 1

                if player.forced_wait_remaining > 0:
                    player.forced_wait_remaining -= 1

                if player.collision_penalty_remaining > 0:
                    player.collision_penalty_remaining -= 1


    def _restitute_ball(
            self,
            match: Match,
            side: Side,
    ) -> None:
        participation = (
            match.participation_a
            if side == Side.LEFT
            else match.participation_b
        )

        closest_player = min(
            (
                player
                for player in participation.players
                if player.is_on_field
            ),
            key=lambda player: distance(
                FIELD_CENTER,
                player.position
            ),
        )

        direction = direction_to(
            FIELD_CENTER,
            closest_player.position,
        )

        match.ball.position = FIELD_CENTER
        match.ball.velocity = (
            direction[0] * RESTART_BALL_SPEED,
            direction[1] * RESTART_BALL_SPEED,
        )


    def _get_on_field_players(
        self,
        snapshot: MatchSnapshot,
    ) -> dict[int, PlayerInMatchSnapshot]:
        return {
            player.player_id: player
            for player in snapshot.players_a + snapshot.players_b
            if player.is_on_field
        }
        

    def _clamp_player_position(
        self,
        position: Position,
    ) -> Position:
        x, y = position

        clamped_x = min(
            max(x, PLAYER_RADIUS),
            FIELD_WIDTH - PLAYER_RADIUS,
        )

        clamped_y = min(
            max(y, PLAYER_RADIUS),
            FIELD_HEIGHT - PLAYER_RADIUS,
        )

        return (clamped_x, clamped_y)
    

    def _get_player_side(
        self,
        snapshot: MatchSnapshot,
        player_id: int,
    ) -> Side:
        if any(
            player.player_id == player_id
            for player in snapshot.players_a
        ):
            return Side.LEFT

        return Side.RIGHT


    def _can_attempt_kick(
        self,
        player: PlayerInMatchSnapshot,
        ball_position: Position,
    ) -> bool:
        if player.forced_wait_remaining > 0:
            return False

        if player.kick_cooldown_remaining > 0:
            return False

        effective_control_range = effective_physical_value(
            player.control,
            player.collision_penalty_remaining,
            control_range,
        )

        return (
            distance(
                player.position,
                ball_position,
            )
            <= effective_control_range
        )


    def _kick_contest_key(
        self,
        snapshot: MatchSnapshot,
        player: PlayerInMatchSnapshot,
    ) -> tuple[float, float, int, int, int]:
        effective_control = effective_physical_value(
            player.control,
            player.collision_penalty_remaining,
            control_range,
        )

        effective_speed = effective_physical_value(
            player.speed,
            player.collision_penalty_remaining,
            max_move_speed,
        )

        player_side = self._get_player_side(
            snapshot,
            player.player_id,
        )

        last_conceding_advantage = (
            1
            if player_side == snapshot.last_conceding_side
            else 0
        )

        return (
            effective_control,
            effective_speed,
            player.strength,
            last_conceding_advantage,
            -player.player_id,
        )


    def _collision_contest_key(
        self,
        player: PlayerInMatchSnapshot,
    ) -> tuple[int, float, float, int]:
        effective_power = effective_physical_value(
            player.power,
            player.collision_penalty_remaining,
            max_kick_force,
        )

        effective_speed = effective_physical_value(
            player.speed,
            player.collision_penalty_remaining,
            max_move_speed,
        )

        return (
            player.strength,
            effective_power,
            effective_speed,
            -player.player_id,
        )


    def _group_collision_events(
        self,
        collisions: list[tuple[float, int, int]],
    ) -> list[tuple[float, set[int]]]:
        events: list[tuple[float, set[int]]] = []

        for time, player_a_id, player_b_id in collisions:
            merged_players = {
                player_a_id,
                player_b_id,
            }

            remaining_events = []

            for event_time, player_ids in events:
                if (
                    isclose(time, event_time)
                    and merged_players & player_ids
                ):
                    merged_players.update(player_ids)
                else:
                    remaining_events.append(
                        (
                            event_time,
                            player_ids,
                        )
                    )

            remaining_events.append(
                (
                    time,
                    merged_players,
                )
            )

            events = remaining_events

        return events


    def _resolve_collision_contest(
        self,
        players: list[PlayerInMatchSnapshot],
    ) -> ContestResolution:
        winner = max(
            players,
            key=self._collision_contest_key,
        )

        loser_ids = tuple(
            player.player_id
            for player in players
            if player.player_id != winner.player_id
        )

        return ContestResolution(
            winner_id=winner.player_id,
            loser_ids=loser_ids,
        )
    

    def _ball_state_after_kick(
        self,
        ball_state: BallState,
        action: KickAction,
        effective_power: float,
    ) -> BallState:
        position, velocity = ball_state

        kick_force = (
            effective_power
            * action.kick_force_factor
        )

        kick_velocity = calculate_kick_velocity(
            velocity,
            action.kick_direction,
            kick_force,
        )

        return (
            position,
            kick_velocity,
        )


    def _is_inside_goal_opening(
        self,
        y: float,
    ) -> bool:
        goal_top = (
            FIELD_HEIGHT - GOAL_WIDTH
        ) / 2

        goal_bottom = (
            FIELD_HEIGHT + GOAL_WIDTH
        ) / 2

        return goal_top <= y <= goal_bottom

    
    def _first_ball_boundary_event(
        self,
        start: Position,
        end: Position,
    ) -> tuple[float, str] | None:
        delta_x = end[0] - start[0]
        delta_y = end[1] - start[1]

        events: list[tuple[float, str]] = []

        # Left side.
        if delta_x < 0.0:
            # First check the physical wall at x = BALL_RADIUS.
            time = (
                BALL_RADIUS - start[0]
            ) / delta_x

            if 0.0 <= time <= 1.0:
                y = start[1] + time * delta_y

                if not self._is_inside_goal_opening(y):
                    events.append(
                        (time, "left")
                    )

            # If the ball passes through the opening,
            # it may reach the goal line at x = 0.
            goal_time = (
                0.0 - start[0]
            ) / delta_x

            if 0.0 <= goal_time <= 1.0:
                y = start[1] + goal_time * delta_y

                if self._is_inside_goal_opening(y):
                    events.append(
                        (goal_time, "goal_left")
                    )

        # Right side.
        if delta_x > 0.0:
            time = (
                FIELD_WIDTH - BALL_RADIUS - start[0]
            ) / delta_x

            if 0.0 <= time <= 1.0:
                y = start[1] + time * delta_y

                if not self._is_inside_goal_opening(y):
                    events.append(
                        (time, "right")
                    )

            goal_time = (
                FIELD_WIDTH - start[0]
            ) / delta_x

            if 0.0 <= goal_time <= 1.0:
                y = start[1] + goal_time * delta_y

                if self._is_inside_goal_opening(y):
                    events.append(
                        (goal_time, "goal_right")
                    )

        # Top wall.
        if delta_y < 0.0:
            time = (
                BALL_RADIUS - start[1]
            ) / delta_y

            if 0.0 <= time <= 1.0:
                events.append(
                    (time, "top")
                )

        # Bottom wall.
        if delta_y > 0.0:
            time = (
                FIELD_HEIGHT - BALL_RADIUS - start[1]
            ) / delta_y

            if 0.0 <= time <= 1.0:
                events.append(
                    (time, "bottom")
                )

        if not events:
            return None

        return min(
            events,
            key=lambda event: event[0],
        )


    def _bounce_ball_velocity(
        self,
        velocity: tuple[float, float],
        boundary: str,
    ) -> tuple[float, float]:
        vx, vy = velocity

        if boundary in ("left", "right"):
            vx = -vx

        if boundary in ("top", "bottom"):
            vy = -vy

        return (
            vx * WALL_BOUNCE_SPEED_FACTOR,
            vy * WALL_BOUNCE_SPEED_FACTOR,
        )


    def _resolve_ball_movement(
        self,
        ball_state: BallState,
    ) -> BallState:
        remaining_time = TIC_DURATION

        while remaining_time > 0.0:
            start_position, _ = ball_state

            free_position, free_velocity = calculate_ball_state_after(
                ball_state,
                remaining_time,
            )

            boundary_event = self._first_ball_boundary_event(
                start_position,
                free_position,
            )

            if boundary_event is None:
                return (
                    free_position,
                    free_velocity,
                )

            event_time, boundary = boundary_event

            event_duration = (
                remaining_time
                * event_time
            )

            _, impact_velocity = calculate_ball_state_after(
                ball_state,
                event_duration,
            )

            impact_position = position_at_time(
                start_position,
                free_position,
                event_time,
            )

            if boundary in (
                "goal_left",
                "goal_right",
            ):
                return (
                    impact_position,
                    impact_velocity,
                )

            rebound_velocity = self._bounce_ball_velocity(
                impact_velocity,
                boundary,
            )

            ball_state = (
                impact_position,
                rebound_velocity,
            )

            remaining_time -= event_duration

        return ball_state


    def _is_goal_restart_ending(
        self,
        match: Match,
    ) -> bool:
        if match.last_conceding_side is None:
            return False

        on_field_players = [
            player
            for participation in (
                match.participation_a,
                match.participation_b,
            )
            for player in participation.players
            if player.is_on_field
        ]

        return all(
            player.forced_wait_remaining == 1
            for player in on_field_players
        )