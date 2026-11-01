from app.game.models.runtime_behavior import RuntimeBehavior, RuntimeCoachBehavior
from app.game.models.actions import MoveAction, KickAction, WaitAction
from app.game.context import BehaviorContext, CoachContext
from app.game.behavior_executor import execute_behavior, execute_coach_behavior
from app.game.types import Assignment


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
        # separate registry: coach ids come from another table and
        # could collide with player behavior ids
        self._coach_behaviors: dict[int, RuntimeCoachBehavior] = {}

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

    def register_coach_behavior(
        self,
        coach_behavior_id: int,
        runtime_coach_behavior: RuntimeCoachBehavior,
    ) -> None:
        """
        Register or replace a runtime coach behavior in the worker.

        Args:
            coach_behavior_id: Identifier used to retrieve the coach behavior.
            runtime_coach_behavior: Executable runtime representation of the coach.
        """
        self._coach_behaviors[coach_behavior_id] = runtime_coach_behavior

    def execute_coach(
        self,
        coach_behavior_id: int,
        context: CoachContext,
    ) -> list[Assignment]:
        """
        Execute a registered coach behavior using the given context.

        Args:
            coach_behavior_id: Identifier of the coach behavior to execute.
            context: State exposed to the coach for the current tic.

        Returns:
            The assignments produced by the coach executor, or an empty
            list if the coach behavior is not registered in this worker.
        """
        runtime_coach_behavior = self._coach_behaviors.get(coach_behavior_id)

        if runtime_coach_behavior is None:
            return []

        return execute_coach_behavior(
            context,
            runtime_coach_behavior,
        )
