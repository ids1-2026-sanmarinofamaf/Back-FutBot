
from dataclasses import dataclass
from multiprocessing import Process, Queue
from queue import Empty
from time import monotonic

from app.game.models.behavior_definition import BehaviorDefinition
from app.game.behavior_compiler import BehaviorCompiler, BehaviorCompilationError
from app.game.models.actions import MoveAction, KickAction, WaitAction
from app.game.context import BehaviorContext, CoachContext
from app.game.types import Assignment
from app.game.behavior_worker import BehaviorWorker


Action = MoveAction | KickAction | WaitAction


@dataclass(frozen=True)
class BehaviorJob:
    """
    Represent a behavior execution request for one player.

    Attributes:
        player_id: Identifier of the player whose behavior must be executed.
        behavior_id: Identifier of the behavior assigned to the player.
        context: BehaviorContext visible to the behavior during the current tic.
    """
    player_id: int
    behavior_id: int
    context: BehaviorContext


@dataclass(frozen=True)
class CoachJob:
    """
    Represent a coach (DT) execution request for one club.

    Attributes:
        club_id: Identifier of the club whose coach must be executed.
        coach_behavior_id: Identifier of the coach behavior chosen by the club.
        context: CoachContext visible to the coach during the current tic.
    """
    club_id: int
    coach_behavior_id: int
    context: CoachContext


class BehaviorWorkerPool:
    """
    Manage a pool of persistent behavior worker processes.

    The pool maintains a fixed number of worker processes capable of executing
    behaviors concurrently. Available behaviors are registered in every worker
    so any worker can execute any player's behavior.

    The pool also enforces a common execution deadline for all jobs in a tic.
    Workers that fail to respond before the deadline are terminated and
    replaced.
    """
    def __init__(self, size: int = 6, timeout_ms: int = 100) -> None:
        """
        Initialize and start the worker pool.

        Args:
            size: Number of persistent worker processes.
            timeout_ms: Maximum execution time shared by all behavior jobs
                dispatched for a tic, in milliseconds.
        """
        self._size = size
        self._timeout_seconds = timeout_ms/1000

        self._processes = []
        self._input_queues = []
        self._output_queues = []

        self._registered_behaviors: dict[int, BehaviorDefinition] = {}
        self._registered_coach_behaviors: dict[int, BehaviorDefinition] = {}

        self._start_workers()


    def _start_workers(self) -> None:
        """
        Start all worker processes configured for the pool.
        """
        for _ in range(self._size):
            self._start_worker()


    def _start_worker(self) -> None:
        """
        Create and start one persistent worker process.

        The worker receives commands through its input queue and returns
        execution results through its output queue.
        """
        input_queue = Queue()
        output_queue = Queue()

        process = Process(
            target=self._worker_loop,
            args=(input_queue, output_queue),
        )

        self._input_queues.append(input_queue)
        self._output_queues.append(output_queue)
        self._processes.append(process)

        process.start()


    @staticmethod
    def _worker_loop(
        input_queue,
        output_queue,
    ) -> None:
        """
        Run the persistent loop executed inside a worker process.

        The loop waits for commands from the pool through the input queue.
        It keeps a local BehaviorWorker instance alive so registered behaviors
        remain available across multiple executions.

        Supported commands:
            "register": Register or replace a RuntimeBehavior.
            "execute": Execute a registered behavior with a BehaviorContext.
            "register_coach": Register or replace a RuntimeCoachBehavior.
            "execute_coach": Execute a registered coach with a CoachContext.
            "shutdown": Stop the worker process.

        Args:
            input_queue: Queue used to receive commands from the pool.
            output_queue: Queue used to send execution results back to the pool.
        """    
        worker = BehaviorWorker()
        compiler = BehaviorCompiler()

        while True:
            message = input_queue.get()

            command = message["command"]

            if command == "register":
                definition = BehaviorDefinition(
                    message["behavior_id"],
                    message["code"],
                )

                runtime_behavior = compiler.compile(definition)

                worker.register_behavior(
                    definition.id,
                    runtime_behavior
                )

            elif command == "execute":
                action = worker.execute(
                    message["behavior_id"],
                    message["context"],
                )

                output_queue.put(
                    {
                        "player_id": message["player_id"],
                        "action": action,
                    }
                )

            elif command == "register_coach":
                definition = BehaviorDefinition(
                    message["coach_behavior_id"],
                    message["code"],
                )

                # an invalid coach is skipped instead of killing the worker;
                # executing it later returns no assignments
                try:
                    runtime_coach_behavior = compiler.compile(
                        definition,
                        entrypoint="coach",
                    )
                except BehaviorCompilationError:
                    continue

                worker.register_coach_behavior(
                    definition.id,
                    runtime_coach_behavior,
                )

            elif command == "execute_coach":
                assignments = worker.execute_coach(
                    message["coach_behavior_id"],
                    message["context"],
                )

                output_queue.put(
                    {
                        "club_id": message["club_id"],
                        "assignments": assignments,
                    }
                )

            elif command == "shutdown":
                break
            

    def register_behaviors(
        self,
        behaviors: list[BehaviorDefinition],
    ) -> None:
        """
        Register the available behaviors in every worker process.

        Every worker receives every behavior so jobs can be assigned to any
        available worker. Behaviors with an existing identifier are replaced.

        The pool also keeps a local copy of the registrations so a replacement
        worker can restore the same registry.

        Args:
            behaviors: Serializable behavior definitions that must be
            available to all workers.
        """
        for behavior in behaviors:
            self._registered_behaviors[behavior.id] = behavior

        for input_queue in self._input_queues:
            for behavior in behaviors:
                input_queue.put(
                    {
                        "command": "register",
                        "behavior_id": behavior.id,
                        "code": behavior.code,
                    }
                )


    def register_coach_behaviors(
        self,
        coach_behaviors: list[BehaviorDefinition],
    ) -> None:
        """
        Register the coach behaviors of the match in every worker process.

        Coach behaviors are kept in a separate registry from player
        behaviors, since their identifiers come from another table.

        Args:
            coach_behaviors: Serializable coach behavior definitions that
            must be available to all workers.
        """
        for coach_behavior in coach_behaviors:
            self._registered_coach_behaviors[coach_behavior.id] = coach_behavior

        for input_queue in self._input_queues:
            for coach_behavior in coach_behaviors:
                input_queue.put(
                    {
                        "command": "register_coach",
                        "coach_behavior_id": coach_behavior.id,
                        "code": coach_behavior.code,
                    }
                )


    def execute(
        self,
        jobs: list[BehaviorJob],
    ) -> dict[int, Action]:
        """
        Execute behavior jobs concurrently using the worker pool.

        Each job is assigned to one worker. All submitted jobs share the same
        execution deadline rather than receiving an independent timeout.

        If a worker does not return before the deadline, its player receives
        WaitAction. The unresponsive worker is then terminated and replaced.

        Args:
            jobs: Behavior execution requests for the current tic.

        Returns:
            A mapping from player identifiers to their resulting actions.

        Raises:
            ValueError: If more jobs are submitted than available workers.
        """
        if len(jobs) > self._size:
            raise ValueError("More jobs than available workers")

        for job, input_queue in zip(jobs, self._input_queues):
            input_queue.put(
                {
                    "command": "execute",
                    "player_id": job.player_id,
                    "behavior_id": job.behavior_id,
                    "context": job.context
                }
            )

        deadline = monotonic() + self._timeout_seconds

        actions: dict[int, Action] = {}

        for index, (job, output_queue) in enumerate(
            zip(jobs, self._output_queues)
        ):
            remaining_time = max(
                0.0,
                deadline - monotonic(),
            )

            try:
                message = output_queue.get(
                    timeout = remaining_time,
                )

                actions[message["player_id"]] = message["action"]

            except Empty:
                actions[job.player_id] = WaitAction()

                process = self._processes[index]

                process.terminate()
                process.join()

                self._replace_worker(index)

        return actions


    def execute_coach(
        self,
        jobs: list[CoachJob],
    ) -> list[list[Assignment]]:
        """
        Execute coach jobs concurrently using the worker pool.

        Works like execute(): each job is assigned to one worker and all
        jobs share the same deadline. If a worker does not return before
        the deadline, its coach produces no assignments and the worker is
        replaced.

        Args:
            jobs: Coach execution requests for the current tic.

        Returns:
            The assignments of each job, in the same order as the jobs.

        Raises:
            ValueError: If more jobs are submitted than available workers.
        """
        if len(jobs) > self._size:
            raise ValueError("More jobs than available workers")

        for job, input_queue in zip(jobs, self._input_queues):
            input_queue.put(
                {
                    "command": "execute_coach",
                    "club_id": job.club_id,
                    "coach_behavior_id": job.coach_behavior_id,
                    "context": job.context,
                }
            )

        deadline = monotonic() + self._timeout_seconds

        results: list[list[Assignment]] = []

        for index, output_queue in enumerate(
            self._output_queues[:len(jobs)]
        ):
            remaining_time = max(
                0.0,
                deadline - monotonic(),
            )

            try:
                message = output_queue.get(
                    timeout = remaining_time,
                )

                results.append(message["assignments"])

            except Empty:
                results.append([])

                process = self._processes[index]

                process.terminate()
                process.join()

                self._replace_worker(index)

        return results


    def _replace_worker(self, index: int) -> None:
        """
        Replace a worker process and restore its registered behaviors.

        A new input queue, output queue, and process are created for the given
        worker slot. All behaviors and coach behaviors currently known by the
        pool are then registered in the new worker.

        Args:
            index: Position of the worker to replace.
        """
        input_queue = Queue()
        output_queue = Queue()

        process = Process(
            target=self._worker_loop,
            args=(input_queue, output_queue),
        )

        self._input_queues[index] = input_queue
        self._output_queues[index] = output_queue
        self._processes[index] = process

        process.start()

        for behavior in self._registered_behaviors.values():
            input_queue.put(
                {
                    "command": "register",
                    "behavior_id": behavior.id,
                    "code": behavior.code,
                }
            )

        for coach_behavior in self._registered_coach_behaviors.values():
            input_queue.put(
                {
                    "command": "register_coach",
                    "coach_behavior_id": coach_behavior.id,
                    "code": coach_behavior.code,
                }
            )


    def shutdown(self) -> None:
        """
        Shut down all worker processes and release pool resources.

        A shutdown command is sent to every active worker. The method then waits
        for each process to finish. If a process does not terminate normally, it
        is forcefully terminated.
        """
        for input_queue in self._input_queues:
            input_queue.put(
                {
                    "command": "shutdown",
                }
            )

        for process in self._processes:
            process.join(timeout=1.0)

            if process.is_alive():
                process.terminate()
                process.join()
