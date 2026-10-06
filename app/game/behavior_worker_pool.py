
from dataclasses import dataclass
from multiprocessing import Process, Queue
from queue import Empty
from time import monotonic

from app.game.models.behavior_definition import BehaviorDefinition
from app.game.behavior_compiler import BehaviorCompiler
from app.game.models.actions import MoveAction, KickAction, WaitAction
from app.game.context import BehaviorContext
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
    

    def _replace_worker(self, index: int) -> None:
        """
        Replace a worker process and restore its registered behaviors.

        A new input queue, output queue, and process are created for the given
        worker slot. All behaviors currently known by the pool are then registered
        in the new worker.

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
