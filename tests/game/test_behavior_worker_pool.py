from textwrap import dedent
from time import monotonic

import pytest

from app.game.behavior_worker_pool import BehaviorJob, BehaviorWorkerPool
from app.game.default_behaviors import (
    ATTACKER_CODE,
    DEFENDER_CODE,
    MIDFIELDER_CODE,
)
from app.game.models.actions import MoveAction, WaitAction
from app.game.models.behavior_definition import BehaviorDefinition


@pytest.fixture
def pool_attacker_behavior():
    return BehaviorDefinition(
        id=101,
        code=ATTACKER_CODE,
    )


@pytest.fixture
def pool_midfielder_behavior():
    return BehaviorDefinition(
        id=102,
        code=MIDFIELDER_CODE,
    )


@pytest.fixture
def pool_defender_behavior():
    return BehaviorDefinition(
        id=103,
        code=DEFENDER_CODE,
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
    pool_midfielder_behavior,
):
    pool = BehaviorWorkerPool(size=1)

    try:
        pool.register_behaviors([
            pool_midfielder_behavior,
        ])

        jobs = [
            BehaviorJob(
                player_id=10,
                behavior_id=pool_midfielder_behavior.id,
                context=context,
            )
        ]

        actions = pool.execute(jobs)

        assert isinstance(actions[10], MoveAction)

    finally:
        pool.shutdown()


def test_pool_executes_multiple_jobs(
    context,
    pool_attacker_behavior,
    pool_midfielder_behavior,
    pool_defender_behavior,
):
    pool = BehaviorWorkerPool(size=3)

    try:
        pool.register_behaviors([
            pool_attacker_behavior,
            pool_midfielder_behavior,
            pool_defender_behavior,
        ])

        jobs = [
            BehaviorJob(
                player_id=1,
                behavior_id=pool_attacker_behavior.id,
                context=context,
            ),
            BehaviorJob(
                player_id=2,
                behavior_id=pool_midfielder_behavior.id,
                context=context,
            ),
            BehaviorJob(
                player_id=3,
                behavior_id=pool_defender_behavior.id,
                context=context,
            ),
        ]

        actions = pool.execute(jobs)

        assert len(actions) == 3
        assert 1 in actions
        assert 2 in actions
        assert 3 in actions

    finally:
        pool.shutdown()


def test_pool_raises_if_jobs_exceed_worker_count(
    context,
    pool_midfielder_behavior,
):
    pool = BehaviorWorkerPool(size=1)

    try:
        pool.register_behaviors([
            pool_midfielder_behavior,
        ])

        jobs = [
            BehaviorJob(
                player_id=1,
                behavior_id=pool_midfielder_behavior.id,
                context=context,
            ),
            BehaviorJob(
                player_id=2,
                behavior_id=pool_midfielder_behavior.id,
                context=context,
            ),
        ]

        with pytest.raises(ValueError):
            pool.execute(jobs)

    finally:
        pool.shutdown()


def test_pool_returns_wait_action_on_timeout(context):
    behavior = BehaviorDefinition(
        id=99,
        code=dedent(
            """
            def play():
                while True:
                    pass
            """
        ),
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
    behavior = BehaviorDefinition(
        id=99,
        code=dedent(
            """
            def play():
                while True:
                    pass
            """
        ),
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
    behavior = BehaviorDefinition(
        id=99,
        code=dedent(
            """
            from time import sleep

            def play():
                sleep(0.1)
                return wait()
            """
        ),
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