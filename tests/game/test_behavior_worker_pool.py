"""Tests for the shared, match-affine BehaviorWorkerPool."""

from concurrent.futures import ThreadPoolExecutor
import multiprocessing as mp

import pytest

from app.game.behavior_worker_pool import BehaviorWorkerPool
from app.game.models.actions import MoveAction, WaitAction
from app.game.models.behavior_definition import BehaviorDefinition
from app.game.models.behavior_job import BehaviorJob


MOVE_CODE = """
def play():
    return move((1.0, 0.0), 1.0)
"""

COUNTER_CODE = """
COUNTER = 0

def play():
    global COUNTER
    COUNTER += 1
    if COUNTER == 1:
        return move((1.0, 0.0), 1.0)
    return wait()
"""

WAIT_CODE = """
def play():
    return wait()
"""

LOOP_CODE = """
def play():
    while True:
        pass
"""


def make_job(player_id, behavior_id, context):
    return BehaviorJob(
        player_id=player_id,
        behavior_id=behavior_id,
        context=context,
    )


@pytest.fixture
def pool():
    # Larger than production's 100ms: these tests exercise IPC, not its latency budget.
    worker_pool = BehaviorWorkerPool(size=2, timeout_ms=2000)
    try:
        yield worker_pool
    finally:
        worker_pool.shutdown()


def test_pool_starts_six_forkserver_workers():
    worker_pool = BehaviorWorkerPool(size=6, timeout_ms=2000)
    try:
        assert worker_pool._context.get_start_method() == "forkserver"
        assert len(worker_pool._processes) == 6
        assert all(
            process.is_alive()
            for process in worker_pool._processes
        )
        assert len({
            process.pid
            for process in worker_pool._processes
        }) == 6
    finally:
        worker_pool.shutdown()


def test_register_match_assigns_stable_worker_and_balances(pool):
    for match_id in (10, 11, 12, 13, 14):
        pool.register_match(match_id, [BehaviorDefinition(100, MOVE_CODE)])

    assignments = dict(pool._match_workers)
    assert assignments == {10: 0, 11: 1, 12: 0, 13: 1, 14: 0}
    assert pool._match_workers == assignments


def test_register_match_rejects_duplicate(pool):
    pool.register_match(10, [BehaviorDefinition(100, MOVE_CODE)])
    with pytest.raises(ValueError, match="already registered"):
        pool.register_match(10, [BehaviorDefinition(100, MOVE_CODE)])


def test_execute_batch_returns_actions_for_six_players(pool, context):
    pool.register_match(10, [BehaviorDefinition(100, MOVE_CODE)])
    jobs = [make_job(player_id, 100, context) for player_id in range(1, 7)]

    actions = pool.execute(jobs, match_id=10)

    assert set(actions) == set(range(1, 7))
    assert all(isinstance(action, MoveAction) for action in actions.values())


def test_unregistered_behavior_returns_wait(pool, context):
    pool.register_match(10, [])

    actions = pool.execute([make_job(1, 999, context)], match_id=10)

    assert isinstance(actions[1], WaitAction)


def test_pool_preserves_state_per_player_and_per_match(context):
    worker_pool = BehaviorWorkerPool(size=1, timeout_ms=2000)
    try:
        definition = BehaviorDefinition(100, COUNTER_CODE)
        worker_pool.register_match(10, [definition])
        worker_pool.register_match(11, [definition])

        first_tick = worker_pool.execute(
            [make_job(1, 100, context), make_job(2, 100, context)],
            match_id=10,
        )
        assert isinstance(first_tick[1], MoveAction)
        assert isinstance(first_tick[2], MoveAction)

        second_tick = worker_pool.execute(
            [make_job(1, 100, context), make_job(2, 100, context)],
            match_id=10,
        )
        assert isinstance(second_tick[1], WaitAction)
        assert isinstance(second_tick[2], WaitAction)

        other_match = worker_pool.execute(
            [make_job(1, 100, context)],
            match_id=11,
        )
        assert isinstance(other_match[1], MoveAction)
    finally:
        worker_pool.shutdown()


def test_switching_behavior_preserves_previous_state(pool, context):
    pool.register_match(
        10,
        [BehaviorDefinition(100, COUNTER_CODE), BehaviorDefinition(101, MOVE_CODE)],
    )
    first = pool.execute(
        [make_job(1, 100, context)],
        match_id=10,
    )
    switched = pool.execute(
        [make_job(1, 101, context)],
        match_id=10,
    )
    returned = pool.execute(
        [make_job(1, 100, context)],
        match_id=10,
    )

    assert isinstance(first[1], MoveAction)
    assert isinstance(switched[1], MoveAction)
    assert isinstance(returned[1], WaitAction)


def test_release_match_keeps_others_working(context):
    worker_pool = BehaviorWorkerPool(size=1, timeout_ms=2000)
    try:
        definition = BehaviorDefinition(100, MOVE_CODE)
        worker_pool.register_match(10, [definition])
        worker_pool.register_match(11, [definition])
        worker_pool.release_match(10)

        with pytest.raises(KeyError):
            worker_pool.execute(
                [make_job(1, 100, context)],
                match_id=10,
            )

        actions = worker_pool.execute(
            [make_job(1, 100, context)],
            match_id=11,
        )
        assert isinstance(actions[1], MoveAction)
    finally:
        worker_pool.shutdown()


def test_worker_restarts_and_restores_matches(context):
    worker_pool = BehaviorWorkerPool(size=1, timeout_ms=2000)
    try:
        worker_pool.register_match(
            10,
            [BehaviorDefinition(100, COUNTER_CODE)],
        )
        first = worker_pool.execute(
            [make_job(1, 100, context)],
            match_id=10,
        )
        assert isinstance(first[1], MoveAction)
        original_process = worker_pool._processes[0]
        original_pid = original_process.pid

        original_process.terminate()
        original_process.join(timeout=2)
        assert not original_process.is_alive()

        restored = worker_pool.execute(
            [make_job(1, 100, context)],
            match_id=10,
        )
        assert isinstance(restored[1], MoveAction)
        assert worker_pool._processes[0].pid != original_pid
        assert worker_pool._processes[0].is_alive()
    finally:
        worker_pool.shutdown()


def test_timeout_does_not_stop_other_players(pool, context):
    pool.register_match(
        10,
        [BehaviorDefinition(100, LOOP_CODE), BehaviorDefinition(101, MOVE_CODE)],
    )
    actions = pool.execute(
        [
            make_job(1, 100, context),
            make_job(2, 101, context),
        ],
        match_id=10,
    )
    assert isinstance(actions[1], WaitAction)
    assert isinstance(actions[2], MoveAction)


def test_concurrent_matches_on_same_worker_do_not_mix_responses(context):
    worker_pool = BehaviorWorkerPool(size=1, timeout_ms=2000)
    try:
        definition = BehaviorDefinition(100, MOVE_CODE)
        worker_pool.register_match(10, [definition])
        worker_pool.register_match(11, [definition])
        with ThreadPoolExecutor(max_workers=2) as executor:
            one = executor.submit(
                worker_pool.execute,
                [make_job(1, 100, context)],
                match_id=10,
            )
            two = executor.submit(
                worker_pool.execute,
                [make_job(2, 100, context)],
                match_id=11,
            )
            a, b = one.result(timeout=5), two.result(timeout=5)
        assert set(a) == {1}
        assert set(b) == {2}
        assert isinstance(a[1], MoveAction)
        assert isinstance(b[2], MoveAction)
    finally:
        worker_pool.shutdown()


def test_shutdown_terminates_workers():
    worker_pool = BehaviorWorkerPool(size=2, timeout_ms=2000)
    worker_pids = {
        process.pid
        for process in worker_pool._processes
    }
    worker_pool.shutdown()
    active_pids = {
        process.pid
        for process in mp.active_children()
    }
    assert worker_pids.isdisjoint(active_pids)
    worker_pool.shutdown()  # Idempotent.
