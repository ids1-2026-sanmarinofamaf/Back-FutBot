from dataclasses import dataclass

from app.game.models.match import Match
from app.game.models.actions import MoveAction, KickAction, WaitAction
from app.game.context_builder import MatchSnapshotLike
from app.game.types import Position, Side


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
        ...


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
        ...


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