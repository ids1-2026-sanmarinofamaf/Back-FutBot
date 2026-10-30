import signal

import pytest

from app.game.behavior_worker import BehaviorWorker
from app.game.primitives import self as current_player
from app.game.behavior_timeout import BehaviorTimeout

from app.game.models.runtime_behavior import RuntimeBehavior
from app.game.models.actions import WaitAction
from app.game.models.behavior_job import BehaviorJob


def test_register_and_execute_behavior(context, wait_behavior):
    worker = BehaviorWorker()

    worker.register_behavior(
        wait_behavior.id,
        wait_behavior,
    )

    action = worker.execute(
        wait_behavior.id,
        context,
    )

    assert isinstance(action, WaitAction)


def test_execute_move_behavior(context, move_behavior):
    worker = BehaviorWorker()

    worker.register_behavior(
        move_behavior.id,
        move_behavior,
    )

    action = worker.execute(
        move_behavior.id,
        context,
    )

    assert action == move_behavior.play()


def test_execute_kick_behavior(context, kick_behavior):
    worker = BehaviorWorker()

    worker.register_behavior(
        kick_behavior.id,
        kick_behavior,
    )

    action = worker.execute(
        kick_behavior.id,
        context,
    )

    assert action == kick_behavior.play()


def test_execute_raises_key_error_for_unknown_behavior(context):
    worker = BehaviorWorker()

    with pytest.raises(KeyError):
        worker.execute(
            999,
            context,
        )


def test_register_behavior_replaces_existing_behavior(
    context,
    move_behavior,
    wait_behavior,
):
    worker = BehaviorWorker()

    worker.register_behavior(
        move_behavior.id,
        move_behavior,
    )

    replacement = RuntimeBehavior(
        id=move_behavior.id,
        play=wait_behavior.play,
    )

    worker.register_behavior(
        replacement.id,
        replacement,
    )

    action = worker.execute(
        replacement.id,
        context,
    )

    assert isinstance(action, WaitAction)


def test_execute_batch_runs_behaviors_sequentially(
    context,
    other_context,
):
    worker = BehaviorWorker()
    execution_order = []

    def play():
        player_id, _ = current_player()
        execution_order.append(player_id)
        return WaitAction()

    behavior = RuntimeBehavior(id=10, play=play)
    worker.register_behavior(behavior.id, behavior)

    jobs = [
        BehaviorJob(1, 10, context),
        BehaviorJob(7, 10, other_context),
    ]

    actions = worker.execute_batch(jobs)

    assert execution_order == [1, 7]
    assert set(actions) == {1, 7}
    assert all(
        isinstance(action, WaitAction)
        for action in actions.values()
    )


def test_execute_batch_continues_after_execution_error(
    context,
    failing_behavior,
    move_behavior,
):
    worker = BehaviorWorker()

    worker.register_behavior(
        failing_behavior.id,
        failing_behavior,
    )
    worker.register_behavior(
        move_behavior.id,
        move_behavior,
    )

    jobs = [
        BehaviorJob(1, failing_behavior.id, context),
        BehaviorJob(2, move_behavior.id, context),
    ]

    actions = worker.execute_batch(jobs)

    assert isinstance(actions[1], WaitAction)
    assert actions[2] == move_behavior.play()


def test_execute_batch_handles_unknown_behavior(
    context,
    move_behavior,
):
    worker = BehaviorWorker()
    worker.register_behavior(
        move_behavior.id,
        move_behavior,
    )

    jobs = [
        BehaviorJob(1, 999, context),
        BehaviorJob(2, move_behavior.id, context),
    ]

    actions = worker.execute_batch(jobs)

    assert isinstance(actions[1], WaitAction)
    assert actions[2] == move_behavior.play()


def test_execute_batch_with_no_jobs():
    worker = BehaviorWorker()

    assert worker.execute_batch([]) == {}


def test_execute_batch_continues_after_timeout(
    context,
    move_behavior,
):
    worker = BehaviorWorker()

    def infinite_play():
        while True:
            pass

    infinite_behavior = RuntimeBehavior(
        id=99,
        play=infinite_play,
    )

    worker.register_behavior(
        infinite_behavior.id,
        infinite_behavior,
    )

    worker.register_behavior(
        move_behavior.id,
        move_behavior,
    )

    jobs = [
        BehaviorJob(1, 99, context),
        BehaviorJob(2, move_behavior.id, context),
    ]

    actions = worker.execute_batch(
        jobs,
        timeout_ms=50,
    )

    assert isinstance(actions[1], WaitAction)
    assert actions[2] == move_behavior.play()


def test_execute_batch_restores_signal_after_timeout(context):
    worker = BehaviorWorker()

    def infinite_play():
        while True:
            pass

    worker.register_behavior(
        99,
        RuntimeBehavior(
            id=99,
            play=infinite_play,
        ),
    )

    previous_handler = signal.getsignal(signal.SIGALRM)

    actions = worker.execute_batch(
        [BehaviorJob(1, 99, context)],
        timeout_ms=50,
    )

    assert isinstance(actions[1], WaitAction)

    assert signal.getsignal(signal.SIGALRM) == previous_handler

    assert signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0)


@pytest.mark.parametrize("timeout_ms", [0, -1])
def test_execute_batch_rejects_invalid_timeout(
    context,
    timeout_ms,
):
    worker = BehaviorWorker()

    with pytest.raises(ValueError):
        worker.execute_batch(
            [BehaviorJob(1, 99, context)],
            timeout_ms=timeout_ms,
        )
