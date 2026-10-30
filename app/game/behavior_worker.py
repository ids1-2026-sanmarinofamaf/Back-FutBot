from app.game.models.runtime_behavior import RuntimeBehavior
from app.game.models.actions import MoveAction, KickAction, WaitAction
from app.game.models.behavior_job import BehaviorJob

from app.game.context import BehaviorContext
from app.game.behavior_executor import (
    execute_behavior,
    execute_behavior_strict,
)
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

        self._runtime_cache: dict[
            tuple[int, int, int],
            RuntimeBehavior,
        ] = {}

        self._disabled_behaviors: dict[int, set[int]] = {}


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


    def register_player_behavior(
        self,
        match_id: int,
        player_id: int,
        behavior_id: int,
        runtime_behavior: RuntimeBehavior,
    ) -> None:
        """
        Register a compiled behavior instance for a specific player.

        Each instance is isolated by match, player and behavior.
        Replacing an existing instance resets its global state.

        Args:
            match_id: Identifier of the match.
            player_id: Identifier of the player.
            behavior_id: Identifier of the behavior.
            runtime_behavior: Compiled behavior instance.
        """
        key = (match_id, player_id, behavior_id)

        self._runtime_cache[key] = runtime_behavior


    def has_player_behavior(
        self,
        match_id: int,
        player_id: int,
        behavior_id: int,
    ) -> bool:
        """
        Check whether a player has a registered behavior instance.

        Args:
            match_id: Identifier of the match.
            player_id: Identifier of the player.
            behavior_id: Identifier of the behavior.

        Returns:
            True if the behavior instance exists, False otherwise.
        """
        key = (match_id, player_id, behavior_id)

        return key in self._runtime_cache


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
        *,
        match_id: int | None = None,
    ) -> dict[int, Action]:
        """
        Execute player behaviors sequentially with individual timeouts.

        Each behavior is executed independently. Failed or disabled
        behaviors produce WaitAction without interrupting the batch.

        Args:
            jobs: Behavior execution requests for the current tick.
            timeout_ms: Maximum execution time per behavior, in milliseconds.
            match_id: Identifier of the match. If None, uses the legacy registry.

        Returns:
            A dictionary mapping player IDs to their resulting actions.

        Raises:
            ValueError: If timeout_ms is less than or equal to zero.
        """
        if timeout_ms <= 0:
            raise ValueError("timeout_ms must be positive")

        actions: dict[int, Action] = {}

        for job in jobs:
            actions[job.player_id] = self._execute_job(
                job,
                timeout_ms,
                match_id,
            )

        return actions


    def _execute_job(
        self,
        job: BehaviorJob,
        timeout_ms: int,
        match_id: int | None
    ) -> Action:
        """
        """
        if (
            match_id is not None
            and job.behavior_id in self._disabled_behaviors.get(
                match_id,
                set(),
            )
        ):
            return WaitAction()

        try:
            if match_id is None:
                runtime = self._behaviors[job.behavior_id]

            else:
                key = (
                    match_id,
                    job.player_id,
                    job.behavior_id,
                )
                runtime = self._runtime_cache[key]

        except KeyError:
            return WaitAction()

        try:
            with behavior_time_limit(timeout_ms):
                if match_id is None:
                    return execute_behavior(
                        job.context,
                        runtime
                    )
                
                return execute_behavior_strict(job.context, runtime)

        except (
            BehaviorTimeout,
            Exception,
        ):
            if match_id is not None:
                self.disable_behavior(
                    match_id,
                    job.behavior_id,
                )

            return WaitAction()
            

    def release_match(
        self,
        match_id: int,
    ) -> None:
        """
        Remove all cached behavior instances belonging to a match.

        Args:
            match_id: Identifier of the match to release.
        """
        keys_to_remove = [
            key
            for key in self._runtime_cache
            if key[0] == match_id
        ]

        for key in keys_to_remove:
            del self._runtime_cache[key]

        self._disabled_behaviors.pop(match_id, None)


    def disable_behavior(
        self,
        match_id: int,
        behavior_id: int,
    ) -> None:
        """
        Disable a behavior for the remainder of a match.

        Args:
            match_id: Identifier of the match.
            behavior_id: Identifier of the behavior to disable.
        """
        self._disabled_behaviors.setdefault(
            match_id,
            set(),
        ).add(behavior_id)


    def get_disabled_behaviors(
        self,
        match_id: int,
    ) -> set[int]:
        """
        Return the disabled behavior identifiers fot a match.

        Args:
            match_id: Identifier of the match.

        Returns:
            A copy of the disabled behavior identifiers.
        """
        return self._disabled_behaviors.get(
            match_id,
            set(),
        ).copy()