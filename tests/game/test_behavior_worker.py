import pytest

from app.game.behavior_worker import BehaviorWorker
from app.game.models.runtime_behavior import RuntimeBehavior
from app.game.models.actions import WaitAction


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