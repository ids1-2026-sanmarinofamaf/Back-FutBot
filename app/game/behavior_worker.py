from app.game.models.runtime_behavior import RuntimeBehavior
from app.game.models.actions import MoveAction, KickAction, WaitAction
from app.game.context import BehaviorContext
from app.game.behavior_executor import execute_behavior


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
    