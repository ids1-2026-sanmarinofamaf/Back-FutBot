from app.game.behavior_worker_pool import BehaviorWorkerPool, BehaviorJob
from app.game.context_builder import MatchSnapshotLike
from app.game.models.actions import MoveAction, KickAction, WaitAction
from app.game.context_builder import build_behavior_context
from app.game.context import BehaviorContext

Action = MoveAction | KickAction | WaitAction

class BehaviorCoordinator:
    """
    Coordinate behavior execution for the players currently on the field.

    The coordinator translates a match snapshot into behavior execution jobs,
    delegates those jobs to the worker pool, and returns one action per player.
    """
    def __init__(self, worker_pool: BehaviorWorkerPool) -> None:
        self._worker_pool = worker_pool


    def get_actions(
        self,
        match_snapshot: MatchSnapshotLike,
    ) -> dict[int, Action]:
        """
        Return one action for each player currently on the field.

        Players under a forced wait penalty or without an assigned behavior receive
        WaitAction directly. All remaining players are converted into BehaviorJob
        instances and executed through the worker pool.

        Args:
            match_snapshot: Immutable snapshot of the current match state.

        Returns:
            A mapping from each on-field player identifier to the action selected
            for the current tic.

        Raises:
            RuntimeError: If the resulting actions do not match the on-field players.
        """
        actions: dict[int, Action] = {}
        jobs: list[BehaviorJob] = []

        for player in match_snapshot.players_a + match_snapshot.players_b:
            if not player.is_on_field:  #ignore substitute
                continue

            if (
                player.forced_wait_remaining > 0    #Not behavior or penalized
                or player.current_behavior_id is None
            ):
                actions[player.player_id] = WaitAction()
                continue                                    

            context = build_behavior_context(
                match_snapshot,
                player,
            )

            jobs.append(
                BehaviorJob(
                    player_id=player.player_id,
                    behavior_id=player.current_behavior_id,
                    context=context,
                )
            )

        worker_actions = self._worker_pool.execute(jobs)
        actions.update(worker_actions)

        # Check all players in field have an action for next tic
        on_field_player_ids = {
            player.player_id
            for player in match_snapshot.players_a + match_snapshot.players_b
            if player.is_on_field
        }

        if set(actions.keys()) != on_field_player_ids:
            raise RuntimeError(
                "Missing or unexpected actions for on-field players"
            )

        return actions



        