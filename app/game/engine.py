from dataclasses import dataclass

from app.game.models.match import Match
from app.game.models.actions import MoveAction, KickAction, WaitAction
from app.game.context_builder import MatchSnapshotLike, PlayerInMatchSnapshotLike
from app.game.types import Position, Side
from app.game.constants import(
    TIC_DURATION,
    FIELD_HEIGHT,
    FIELD_WIDTH,
    PLAYER_RADIUS
    )
from app.game.physics import(
    max_move_speed,
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


@dataclass(frozen=True)
class CollisionResolution:
    contest: ContestResolution
    collision_positions: dict[int, Position]


class GameEngine:
    """
    Resolve one simulation tic and update the mutable match state.
    """
    def step(
            self,
            match: Match,
            snapshot: MatchSnapshotLike,
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

        kick_result = self._resolve_kicks(
            snapshot,
            actions,
        )

        proposed_positions = self._resolve_moves(
            snapshot,
            actions,
        )

        final_positions = self._resolve_player_collisions(
            snapshot,
            proposed_positions,
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

        self._update_timers(match)



    def _validate_actions(
        self,
        snapshot: MatchSnapshotLike,
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
        snapshot: MatchSnapshotLike,
        actions: dict[int, Action],
    ) -> KickResolution | None:
        ...


    def _resolve_moves(
        self,
        snapshot: MatchSnapshotLike,
        actions: dict[int, Action],
    ) -> dict[int, Position]:
        players = self._get_on_field_players(snapshot)

        proposed_positions = {
            player_id: player.position
            for player_id, player in players.items()
        }

        for player_id, player in players.items():
            action = actions[player_id]

            if not isinstance(action, MoveAction):
                continue

            move_speed = max_move_speed(player.speed)

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
        snapshot: MatchSnapshotLike,
        proposed_positions: dict[int, Position],
    ) -> dict[int, Position]:
        ...


    def _apply_player_positions(
        self,
        match: Match,
        final_positions: dict[int, Position],
    ) -> None:
        ...


    def _update_ball(
        self,
        match: Match,
        snapshot: MatchSnapshotLike,
        kick_result: KickResolution | None,
        final_positions: dict[int, Position],
    ) -> None:
        ...


    def _detect_goal(
        self,
        match: Match,
    ) -> Side | None:
        ...


    def _handle_goal(
        self,
        match: Match,
        conceding_side: Side,
    ) -> None:
        ...


    def _update_timers(
        self,
        match: Match,
    ) -> None:
        ...


    def _get_on_field_players(
        self,
        snapshot: MatchSnapshotLike,
    ) -> dict[int, PlayerInMatchSnapshotLike]:
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