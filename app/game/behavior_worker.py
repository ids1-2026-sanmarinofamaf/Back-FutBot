from app.game.models.runtime_behavior import RuntimeBehavior
from app.game.models.actions import MoveAction, KickAction, WaitAction
from app.game.models.behavior_job import BehaviorJob

from app.game.context import BehaviorContext
from app.game.behavior_executor import execute_behavior
from app.game.behavior_timeout import (
    BehaviorTimeout,
    behavior_time_limit,
)
from app.game.constants import BEHAVIOR_EXECUTION_TIMEOUT_MS


Action = MoveAction | KickAction | WaitAction


class BehaviorWorker:
    """
    Execute registered runtime behaviors for players.

    Each worker maintains a local registry that maps behavior identifiers
    to RuntimeBehavior instances. Behaviors can be registered or replaced
    and later executed using a BehaviorContext.
    """
    def __init__(self) -> None:
        """
        Initialize an empty behavior registry.
        """
        self._behaviors: dict[int, RuntimeBehavior] = {}

    def register_behavior(
        self,
        behavior_id: int,
        runtime_behavior: RuntimeBehavior,
    ) -> None:
        """
        Register or replace a runtime behavior in the worker.

        Args:
            behavior_id: Identifier used to retrieve the behavior.
            runtime_behavior: Executable runtime representation of the behavior.
        """
        self._behaviors[behavior_id] = runtime_behavior

    def execute(
        self,
        behavior_id: int,
        context: BehaviorContext,
    ) -> Action:
        """
        Execute a registered behavior using the given context.

        Args:
            behavior_id: Identifier of the behavior to execute.
            context: State exposed to the behavior for the current tic.

        Returns:
            The action produced by the behavior executor.

        Raises:
            KeyError: If the behavior is not registered in this worker.
        """
        runtime_behavior = self._behaviors[behavior_id]

        return execute_behavior(
            context,
            runtime_behavior,
        )


    def execute_batch(
        self,
        jobs: list[BehaviorJob],
        timeout_ms: int = BEHAVIOR_EXECUTION_TIMEOUT_MS,
    ) -> dict[int, Action]:
        """
        Execute behaviors sequentially with an individual timeout.

        Each behavior runs with its own context and execution time limit.
        If a behavior exceeds the timeout or is not registered, the player
        receives a WaitAction without interrupting the remaining jobs.

        Args:
            jobs: List of behaviors executions requests for the current tic.
            timeout_ms: Maximum execution time allowed per behavior in ms.

        Returns:
            A dictionary mapping each player ID to its resulting action.

        Raises:
            ValueError: If timeout_ms is less than or equal to zero.
        """
        if timeout_ms <= 0:
            raise ValueError("timeout_ms must be positive")

        actions: dict[int, Action] = {}

        for job in jobs:
            try:
                with behavior_time_limit(timeout_ms):
                    action = self.execute(
                        job.behavior_id,
                        job.context,
                    )

            except(
                BehaviorTimeout,
                KeyError,
            ):
                action = WaitAction()

            actions[job.player_id] = action

        return actions
    