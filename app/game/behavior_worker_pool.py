import multiprocessing as mp

from collections import Counter
from queue import Empty
from threading import Lock
from time import monotonic
from uuid import uuid4

from app.game.models.behavior_definition import BehaviorDefinition
from app.game.models.actions import MoveAction, KickAction, WaitAction
from app.game.models.behavior_job import BehaviorJob

from app.game.behavior_compiler import BehaviorCompiler, BehaviorCompilationError
from app.game.behavior_worker import BehaviorWorker


Action = MoveAction | KickAction | WaitAction

WORKER_STARTUP_TIMEOUT_SECONDS = 5.0


class BehaviorWorkerPool:
    """
    Executed behavior batches in a shared pool of persistent process.

    Every match is assigned to one worker fot irs entire lifetime, so
    compiled behaviors preserve their per-player state across tics.
    """
    def __init__(self, size: int = 6, timeout_ms: int = 100) -> None:
        """
        Start te worker processes using forkserver.

        Args:
            size: Number of persistent worker processes.
            timeout_ms: Maximum execution time shared by all behavior jobs
                dispatched for a tic, in milliseconds.
        Raises:
            ValueError: If size or timeout_ms is not positive.
        """
        if size <= 0 or timeout_ms <= 0:
            raise ValueError("size and timeout_ms must be positive")

        self._size = size
        self._timeout_seconds = timeout_ms/1000
        self._context = mp.get_context("forkserver")

        self._state_lock = Lock()
        self._registration_lock = Lock()
        self._worker_locks = [
            Lock()
            for _ in range(size)
        ]

        self._match_workers: dict[int, int] = {}
        self._match_definitions: dict[int, list[BehaviorDefinition]] = {}
        self._disabled_behaviors: dict[int, set[int]] = {}
        self._closed = False

        self._processes = []
        self._input_queues = []
        self._output_queues = []

        for index in range(size):
            self._start_worker(index)


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
            "register_match": Register definitions for a match.
            "release-match": Release state for a finished match.
            "execute_batch": Execute one match batch.
            "shutdown": Stop the worker process.

        Args:
            input_queue: Queue used to receive commands from the pool.
            output_queue: Queue used to send execution results back to the pool.
        """    
        worker = BehaviorWorker()
        compiler = BehaviorCompiler()
        definitions: dict[int, dict[int, BehaviorDefinition]] = {}

        output_queue.put({
            "status": "ready"
        })

        while True:
            message = input_queue.get()
            command = message["command"]
            match_id = message.get("match_id")

            if command == "shutdown":
                return

            if command == "register_match":
                worker.release_match(match_id)

                definitions[match_id] = {
                    behavior.id: behavior
                    for behavior in message["behaviors"]
                }

                for behavior_id in message.get("disabled_behavior_ids", []):
                    worker.disable_behavior(match_id, behavior_id)

            elif command == "release_match":
                worker.release_match(match_id)
                definitions.pop(match_id, None)

            elif command == "execute_batch":
                jobs = message["jobs"]
                BehaviorWorkerPool._register_missing_behaviors(
                    worker,
                    compiler,
                    match_id,
                    jobs,
                    definitions.get(match_id, {}),
                )

                actions = worker.execute_batch(
                    jobs,
                    match_id=match_id,
                )

                output_queue.put({
                    "request_id": message["request_id"],
                    "match_id": match_id,
                    "actions": actions,
                    "disabled_behavior_ids": sorted(
                        worker.get_disabled_behaviors(match_id)
                    ),
                })


    @staticmethod
    def _register_missing_behaviors(
        worker: BehaviorWorker,
        compiler: BehaviorCompiler,
        match_id: int,
        jobs: list[BehaviorJob],
        definitions: dict[int, BehaviorDefinition],
    ) -> None:
        """
        Compile and register missing player-specific behavior instances

        Args:
            worker: Worker holding compiled runtime instance.
            compiler: Compiler used to create isolated runtime instances.
            match_id: Identifier of the match being executed.
            jobs: Behavior requests for the current tic.
            definitions: Source definitions available to the match.
        """
        disabled = worker.get_disabled_behaviors(match_id)

        for job in jobs:
            if job.behavior_id in disabled:
                continue

            if worker.has_player_behavior(
                match_id,
                job.player_id,
                job.behavior_id,
            ):
                continue

            definition = definitions.get(job.behavior_id)
            if definition is None:
                continue

            try:
                runtime = compiler.compile(definition)

            except BehaviorCompilationError:
                worker.disable_behavior(
                    match_id,
                    job.behavior_id,
                )
                disabled.add(job.behavior_id)
                continue

            worker.register_player_behavior(
                match_id,
                job.player_id,
                job.behavior_id,
                runtime,
            )


    def _start_worker(
        self,
        index: int,
    ) -> None:
        """
        Start a new process in the given worker slot.

        Args:
            index: Worker slot to initialize to replace.
        """
        input_queue = self._context.Queue()
        output_queue = self._context.Queue()
        process = self._context.Process(
            target=self._worker_loop,
            args=(input_queue, output_queue),
            name=f"behavior-worker-{index}",
        )
        process.start()

        if index == len(self._processes):
            self._processes.append(process)
            self._input_queues.append(input_queue)
            self._output_queues.append(output_queue)
        else:
            self._processes[index] = process
            self._input_queues[index] = input_queue
            self._output_queues[index] = output_queue

        try:
            ready = output_queue.get(
                timeout=WORKER_STARTUP_TIMEOUT_SECONDS
            )

            if ready != {"status": "ready"}:
                raise RuntimeError(
                    f"Worker {index} returned an invalid ready message"
                )

        except (
            Empty,
            EOFError,
            OSError,
            ValueError,
            RuntimeError,
        ) as exc:
            self._stop_worker(index, graceful=False)

            raise RuntimeError(
                f"Worker {index} failed to initialize"
            ) from exc


    def _stop_worker(
        self,
        index: int,
        *,
        graceful: bool,
    ) -> None:
        """
        Stop a worker and close its IPC queues.

        Args:
            index: Worker slot to stop.
            graceful: Whether to request shutdown before terminating.
        """
        process = self._processes[index]
        input_queue = self._input_queues[index]
        output_queue = self._output_queues[index]

        if graceful and process.is_alive():
            try:
                input_queue.put({
                    "command": "shutdown"
                })
                process.join(timeout = 0.5)

            except (OSError, ValueError):
                pass

        if process.is_alive():
            process.terminate()
            process.join(timeout=0.2)

        if process.is_alive():
            process.kill()
            process.join()

        for queue in (input_queue, output_queue):
            queue.cancel_join_thread()
            queue.close()

        process.close()


    def _restore_matches(
        self,
        index: int,
    ) -> None:
        """
        Re-register all matches assigned to a replacement process.

        Args:
            index: Worker slot whose matches must be restored.
        """
        with self._state_lock:
            registrations = [
                (
                    match_id,
                    self._match_definitions[match_id],
                    sorted(
                        self._disabled_behaviors.get(
                            match_id,
                            set(),
                        )
                    ),
                )
                for match_id, worker_index in self._match_workers.items()
                if worker_index == index
            ]

        for match_id, behaviors, disabled_ids in registrations:
            self._input_queues[index].put({
                "command": "register_match",
                "match_id": match_id,
                "behaviors": behaviors,
                "disabled_behavior_ids": disabled_ids,
            })


    def _replace_worker(
        self,
        index: int,
    ) -> None:
        """
        Replace a worker process and restore its registered matches.

        Mutable state held by the old process is lost.

        Args:
            index: Worker slot to replace.
        """
        # Caller holds the corresponding _worker_locks[index]
        self._stop_worker(index, graceful=False)
        self._start_worker(index)
        self._restore_matches(index)


    def _select_worker(self) -> int:
        """
        Select the worker with the fewest assigned matches.

        Returns:
            Index of the selected worker.
        """
        #Caller holds _state_lock.
        counts = Counter(self._match_workers.values())
        return min(
            range(self._size),
            key=lambda index: counts[index],
        )


    def register_match(
        self,
        match_id: int,
        behaviors: list[BehaviorDefinition],
    ) -> None:
        """
        Register a match and assign it to a worker for its lifetime.

        Args:
            match_id: Identifier of the match.
            behaviors: Behavior definitions available during the match.

        Raises:
            RuntimeError: If the pool has ben shut down.
            ValueError: If the match is already registered.
        """
        # Keeps selection atomic.
        with self._registration_lock:
            with self._state_lock:
                if self._closed:
                    raise RuntimeError("Behavior worker pool is shut down")

                if match_id in self._match_workers:
                    raise ValueError("Match is already registered")

                index = self._select_worker()

            with self._worker_locks[index]:
                if not self._processes[index].is_alive():
                    self._replace_worker(index)

                with self._state_lock:
                    if self._closed:
                        raise RuntimeError("Behavior worker pool is shut down")

                    self._input_queues[index].put({
                        "command": "register_match",
                        "match_id": match_id,
                        "behaviors": behaviors,
                    })
                    self._match_workers[match_id] = index
                    self._match_definitions[match_id] = list(behaviors)
                    self._disabled_behaviors[match_id] = set()


    def _request_batch(
        self,
        index: int,
        match_id: int,
        jobs: list[BehaviorJob],
        deadline: float,
    ) -> dict[int, Action] | None:
        """
        Send one batch and wait for its correlated response.

        Args:
            index: Worker slot handling the match.
            match_id: Identifier of the match.
            jobs: Behavior requests for the tic.
            deadline: Absolute monotonic deadline for the request.

        Returns:
            Mapped actions, or None if the request fails or times out.
        """
        request_id = uuid4().hex

        try:
            self._input_queues[index].put({
                "command": "execute_batch",
                "request_id": request_id,
                "match_id": match_id,
                "jobs": jobs,
            })

            remaining = deadline - monotonic()
            if remaining <= 0:
                return None
            result = self._output_queues[index].get(timeout=remaining)

        except (
            Empty,
            EOFError,
            OSError,
            ValueError,
        ):
            return None

        if (
            not isinstance(result, dict)
            or result.get("request_id") != request_id
            or result.get("match_id") != match_id
            or not isinstance(result.get("actions"), dict)
        ):
            return None

        with self._state_lock:
            self._disabled_behaviors[match_id].update(
                result["disabled_behavior_ids"]
            )

        return {
            job.player_id: result["actions"].get(
                job.player_id,
                WaitAction()
            )
            for job in jobs
        }


    def execute(
        self,
        jobs: list[BehaviorJob],
        *,
        match_id: int,
    ) -> dict[int, Action]:
        """
        Execute a match batch without exceeding the request deadline.

        Args:
            jobs: Behavior requests for the current tic.
            match_id: Identifier of the registered match.

        Returns:
            A mapping from player identifier to the resulting action.

        Raises:
            KeyError: If the match is not registered.
            RuntimeError: If the pool has been shut down.
        """
        with self._state_lock:
            if self._closed:
                raise RuntimeError("Behavior worker pool is shut down")

            index = self._match_workers[match_id]

        if not jobs:
            return {}

        fallback = {
            job.player_id: WaitAction()
            for job in jobs
        }
        deadline = monotonic() + self._timeout_seconds
        lock = self._worker_locks[index]

        if not lock.acquire(
            timeout=max(
                0.0,
                deadline - monotonic(),
            )
        ):
            return fallback

        try:
            with self._state_lock:
                if (
                    self._closed
                    or self._match_workers.get(match_id) != index
                ):
                    return fallback

            if not self._processes[index].is_alive():
                self._replace_worker(index)

            if monotonic() >= deadline:
                return fallback

            actions = self._request_batch(
                index,
                match_id,
                jobs,
                deadline,
            )

            if actions is None:
                self._replace_worker(index)
                return fallback

            return actions

        finally:
            lock.release()


    def release_match(
        self,
        match_id: int,
    ) -> None:
        """
        Release cached runtime behavior and definitions fot a match.

        Args:
            match_id: Identifier of the finished match.
        """
        with self._state_lock:
            index = self._match_workers.get(match_id)

        if index is None:
            return

        with self._worker_locks[index]:
            with self._state_lock:
                if self._match_workers.get(match_id) != index:
                    return

                self._match_workers.pop(match_id)
                self._match_definitions.pop(match_id, None)
                self._disabled_behaviors.pop(match_id, None)
                closed = self._closed

            if not closed and self._processes[index].is_alive():
                self._input_queues[index].put({
                    "command": "release_match",
                    "match_id": match_id,
                })


    def shutdown(self) -> None:
        """
        Stop all processes and release the pool's state and resources.
        """
        with self._state_lock:
            if self._closed:
                return

            self._closed = True
            self._match_workers.clear()
            self._match_definitions.clear()
            self._disabled_behaviors.clear()

        for index in range(self._size):
            with self._worker_locks[index]:
                self._stop_worker(
                    index,
                    graceful=True,
                )
