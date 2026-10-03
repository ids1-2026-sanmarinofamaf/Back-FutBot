from time import monotonic, sleep

import pytest

from app.game.behavior_worker_pool import BehaviorJob, BehaviorWorkerPool
from app.game.models.actions import MoveAction, WaitAction
from app.game.models.runtime_behavior import RuntimeBehavior


def move_play():
    return MoveAction(
        move_direction=(1.0, 0.0),
        move_speed_factor=1.0,
    )


def wait_play():
    return WaitAction()


def infinite_play():
    while True:
        pass

def slow_play():
    sleep(0.1)
    return WaitAction()

@pytest.fixture
def pool_move_behavior():
    return RuntimeBehavior(
        id=101,
        play=move_play,
    )


@pytest.fixture
def pool_wait_behavior():
    return RuntimeBehavior(
        id=102,
        play=wait_play,
    )


def test_pool_starts_configured_number_of_workers():
    pool = BehaviorWorkerPool(size=3)

    try:
        assert len(pool._processes) == 3
        assert all(process.is_alive() for process in pool._processes)
    finally:
        pool.shutdown()


def test_pool_executes_registered_behavior(
    context,
    pool_wait_behavior,
):
    pool = BehaviorWorkerPool(size=1)

    try:
        pool.register_behaviors([pool_wait_behavior])

        jobs = [
            BehaviorJob(
                player_id=10,
                behavior_id=pool_wait_behavior.id,
                context=context,
            )
        ]

        actions = pool.execute(jobs)

        assert isinstance(actions[10], WaitAction)

    finally:
        pool.shutdown()


def test_pool_executes_multiple_jobs(
    context,
    pool_move_behavior,
    pool_wait_behavior,
):
    pool = BehaviorWorkerPool(size=2)

    try:
        pool.register_behaviors([
            pool_move_behavior,
            pool_wait_behavior,
        ])

        jobs = [
            BehaviorJob(
                player_id=1,
                behavior_id=pool_move_behavior.id,
                context=context,
            ),
            BehaviorJob(
                player_id=2,
                behavior_id=pool_wait_behavior.id,
                context=context,
            ),
        ]

        actions = pool.execute(jobs)

        assert isinstance(actions[1], MoveAction)
        assert isinstance(actions[2], WaitAction)

    finally:
        pool.shutdown()


def test_pool_raises_if_jobs_exceed_worker_count(
    context,
    wait_behavior,
):
    pool = BehaviorWorkerPool(size=1)

    try:
        pool.register_behaviors([wait_behavior])

        jobs = [
            BehaviorJob(1, wait_behavior.id, context),
            BehaviorJob(2, wait_behavior.id, context),
        ]

        with pytest.raises(ValueError):
            pool.execute(jobs)

    finally:
        pool.shutdown()


def test_pool_returns_wait_action_on_timeout(context):
    behavior = RuntimeBehavior(
        id=99,
        play=infinite_play,
    )

    pool = BehaviorWorkerPool(
        size=1,
        timeout_ms=20,
    )

    try:
        pool.register_behaviors([behavior])

        jobs = [
            BehaviorJob(
                player_id=1,
                behavior_id=behavior.id,
                context=context,
            )
        ]

        actions = pool.execute(jobs)

        assert isinstance(actions[1], WaitAction)

    finally:
        pool.shutdown()


def test_pool_replaces_worker_after_timeout(context):
    behavior = RuntimeBehavior(
        id=99,
        play=infinite_play,
    )

    pool = BehaviorWorkerPool(
        size=1,
        timeout_ms=20,
    )

    try:
        original_process = pool._processes[0]

        pool.register_behaviors([behavior])

        pool.execute([
            BehaviorJob(
                player_id=1,
                behavior_id=behavior.id,
                context=context,
            )
        ])

        replacement_process = pool._processes[0]

        assert replacement_process.pid != original_process.pid
        assert replacement_process.is_alive()

    finally:
        pool.shutdown()


def test_shutdown_stops_all_workers():
    pool = BehaviorWorkerPool(size=3)

    processes = list(pool._processes)

    pool.shutdown()

    assert all(
        not process.is_alive()
        for process in processes
    )

def test_pool_returns_wait_action_for_unknown_behavior(context):
    pool = BehaviorWorkerPool(size=1)

    try:
        actions = pool.execute([
            BehaviorJob(
                player_id=1,
                behavior_id=999,
                context=context,
            )
        ])

        assert isinstance(actions[1], WaitAction)

    finally:
        pool.shutdown()


def test_pool_replaces_worker_after_execution_error(context):
    pool = BehaviorWorkerPool(size=1)

    try:
        original_process = pool._processes[0]

        pool.execute([
            BehaviorJob(
                player_id=1,
                behavior_id=999,
                context=context,
            )
        ])

        replacement_process = pool._processes[0]

        assert replacement_process.pid != original_process.pid
        assert replacement_process.is_alive()

    finally:
        pool.shutdown()


def test_pool_uses_common_deadline_for_concurrent_jobs(
    context,
):
    behavior = RuntimeBehavior(
        id=99,
        play=slow_play,
    )

    pool = BehaviorWorkerPool(
        size=6,
        timeout_ms=20,
    )

    try:
        pool.register_behaviors([behavior])

        jobs = [
            BehaviorJob(
                player_id=player_id,
                behavior_id=behavior.id,
                context=context,
            )
            for player_id in range(1, 7)
        ]

        start = monotonic()

        actions = pool.execute(jobs)

        elapsed = monotonic() - start

        assert len(actions) == 6
        assert all(
            isinstance(action, WaitAction)
            for action in actions.values()
        )

        # Six sequential 20 ms timeouts would already require about 120 ms.
        # With a shared deadline the executions timeout concurrently.
        assert elapsed < 0.12

    finally:
        pool.shutdown()