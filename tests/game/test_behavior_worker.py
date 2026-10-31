import signal

import pytest

from textwrap import dedent

from app.game.behavior_worker import BehaviorWorker
from app.game.primitives import self as current_player
from app.game.behavior_compiler import BehaviorCompiler

from app.game.models.runtime_behavior import RuntimeBehavior
from app.game.models.actions import WaitAction, MoveAction
from app.game.models.behavior_job import BehaviorJob
from app.game.models.behavior_definition import BehaviorDefinition


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

    behavior = RuntimeBehavior(
        id=10,
        play=play,
    )

    for player_id in (1, 7):
        worker.register_player_behavior(
            match_id=10,
            player_id=player_id,
            behavior_id=behavior.id,
            runtime_behavior=behavior,
        )

    jobs = [
        BehaviorJob(1, 10, context),
        BehaviorJob(7, 10, other_context),
    ]

    actions = worker.execute_batch(
        jobs,
        match_id=10,
    )

    assert execution_order == [1, 7]
    assert isinstance(actions[1], WaitAction)
    assert isinstance(actions[7], WaitAction)


def test_execute_batch_continues_after_execution_error(
    context,
    other_context,
    failing_behavior,
    move_behavior,
):
    worker = BehaviorWorker()

    worker.register_player_behavior(
        match_id=10,
        player_id=1,
        behavior_id=failing_behavior.id,
        runtime_behavior=failing_behavior,
    )

    worker.register_player_behavior(
        match_id=10,
        player_id=7,
        behavior_id=move_behavior.id,
        runtime_behavior=move_behavior,
    )

    jobs = [
        BehaviorJob(1, failing_behavior.id, context),
        BehaviorJob(7, move_behavior.id, other_context),
    ]

    actions = worker.execute_batch(
        jobs,
        match_id=10,
    )

    assert isinstance(actions[1], WaitAction)
    assert isinstance(actions[7], MoveAction)

    assert worker.get_disabled_behaviors(10) == {
        failing_behavior.id,
    }


def test_execute_batch_handles_unknown_behavior(
    context,
    other_context,
    move_behavior,
):
    worker = BehaviorWorker()

    worker.register_player_behavior(
        match_id=10,
        player_id=1,
        behavior_id=move_behavior.id,
        runtime_behavior=move_behavior,
    )

    jobs = [
        BehaviorJob(1, move_behavior.id, context),
        BehaviorJob(7, 999, other_context),
    ]

    actions = worker.execute_batch(
        jobs,
        match_id=10,
    )

    assert isinstance(actions[1], MoveAction)
    assert isinstance(actions[7], WaitAction)

    # An unknown behavior must not be disabled.
    assert worker.get_disabled_behaviors(10) == set()


def test_execute_batch_with_no_jobs():
    worker = BehaviorWorker()

    assert worker.execute_batch(
        [],
        match_id=10,
    ) == {}


def test_execute_batch_continues_after_timeout(
    context,
    other_context,
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

    worker.register_player_behavior(
        match_id=10,
        player_id=1,
        behavior_id=99,
        runtime_behavior=infinite_behavior,
    )

    worker.register_player_behavior(
        match_id=10,
        player_id=7,
        behavior_id=move_behavior.id,
        runtime_behavior=move_behavior,
    )

    jobs = [
        BehaviorJob(1, 99, context),
        BehaviorJob(7, move_behavior.id, other_context),
    ]

    actions = worker.execute_batch(
        jobs,
        match_id=10,
        timeout_ms=2,
    )

    assert isinstance(actions[1], WaitAction)
    assert isinstance(actions[7], MoveAction)

    assert worker.get_disabled_behaviors(10) == {99}


def test_execute_batch_restores_signal_after_timeout(context):
    worker = BehaviorWorker()

    def infinite_play():
        while True:
            pass

    infinite_behavior = RuntimeBehavior(
        id=99,
        play=infinite_play,
    )

    worker.register_player_behavior(
        match_id=10,
        player_id=1,
        behavior_id=99,
        runtime_behavior=infinite_behavior,
    )

    original_handler = signal.getsignal(signal.SIGALRM)
    original_timer = signal.getitimer(signal.ITIMER_REAL)

    actions = worker.execute_batch(
        [BehaviorJob(1, 99, context)],
        match_id=10,
        timeout_ms=2,
    )

    assert isinstance(actions[1], WaitAction)

    assert signal.getsignal(signal.SIGALRM) == original_handler
    assert signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0)

    assert worker.get_disabled_behaviors(10) == {99}


@pytest.mark.parametrize("timeout_ms", [0, -1])
def test_execute_batch_rejects_invalid_timeout(
    context,
    timeout_ms,
):
    worker = BehaviorWorker()

    with pytest.raises(ValueError):
        worker.execute_batch(
            [BehaviorJob(1, 99, context)],
            match_id=10,
            timeout_ms=timeout_ms,
        )


def compile_counter_behavior():
    definition = BehaviorDefinition(
        id=100,
        code=dedent("""
            COUNTER = 0

            def play():
                global COUNTER
                COUNTER += 1
                return wait()
            """),
    )

    return BehaviorCompiler().compile(definition)


def test_register_player_behavior():
    worker = BehaviorWorker()
    behavior = compile_counter_behavior()

    assert not worker.has_player_behavior(10, 1, 100)

    worker.register_player_behavior(
        match_id=10,
        player_id=1,
        behavior_id=100,
        runtime_behavior=behavior,
    )

    assert worker.has_player_behavior(10, 1, 100)
    assert not worker.has_player_behavior(10, 2, 100)
    assert not worker.has_player_behavior(11, 1, 100)


def test_player_behaviors_have_independent_state(context):
    worker = BehaviorWorker()

    behavior_a = compile_counter_behavior()
    behavior_b = compile_counter_behavior()

    worker.register_player_behavior(10, 1, 100, behavior_a)
    worker.register_player_behavior(10, 2, 100, behavior_b)

    worker.execute_batch(
        [BehaviorJob(1, 100, context)],
        match_id=10,
    )

    worker.execute_batch(
        [BehaviorJob(1, 100, context)],
        match_id=10,
    )

    worker.execute_batch(
        [BehaviorJob(2, 100, context)],
        match_id=10,
    )

    assert behavior_a.play.__globals__["COUNTER"] == 2
    assert behavior_b.play.__globals__["COUNTER"] == 1


def test_matches_have_independent_behavior_state(context):
    worker = BehaviorWorker()

    behavior_match_10 = compile_counter_behavior()
    behavior_match_11 = compile_counter_behavior()

    worker.register_player_behavior(10, 1, 100, behavior_match_10)
    worker.register_player_behavior(11, 1, 100, behavior_match_11)

    job = BehaviorJob(1, 100, context)

    worker.execute_batch([job], match_id=10)
    worker.execute_batch([job], match_id=10)
    worker.execute_batch([job], match_id=11)

    assert behavior_match_10.play.__globals__["COUNTER"] == 2
    assert behavior_match_11.play.__globals__["COUNTER"] == 1


def test_switching_behaviors_preserves_previous_state(context):
    worker = BehaviorWorker()

    behavior_a = compile_counter_behavior()
    behavior_b = compile_counter_behavior()

    worker.register_player_behavior(10, 1, 100, behavior_a)
    worker.register_player_behavior(10, 1, 200, behavior_b)

    worker.execute_batch(
        [BehaviorJob(1, 100, context)],
        match_id=10,
    )

    worker.execute_batch(
        [BehaviorJob(1, 200, context)],
        match_id=10,
    )

    worker.execute_batch(
        [BehaviorJob(1, 100, context)],
        match_id=10,
    )

    assert behavior_a.play.__globals__["COUNTER"] == 2
    assert behavior_b.play.__globals__["COUNTER"] == 1


def test_release_match_only_removes_its_behaviors():
    worker = BehaviorWorker()

    worker.register_player_behavior(
        10, 1, 100, compile_counter_behavior()
    )

    worker.register_player_behavior(
        11, 1, 100, compile_counter_behavior()
    )

    worker.release_match(10)

    assert not worker.has_player_behavior(10, 1, 100)
    assert worker.has_player_behavior(11, 1, 100)


def test_behavior_failure_disables_it_for_match(
    context,
    other_context,
):
    worker = BehaviorWorker()

    definition = BehaviorDefinition(
        id=100,
        code=dedent("""
            def play():
                if self()[0] == 1:
                    raise RuntimeError("Behavior failed")

                return move((1.0, 0.0), 1.0)
            """),
    )

    compiler = BehaviorCompiler()

    worker.register_player_behavior(
        10, 1, 100, compiler.compile(definition)
    )

    worker.register_player_behavior(
        10, 7, 100, compiler.compile(definition)
    )

    actions = worker.execute_batch(
        [
            BehaviorJob(1, 100, context),
            BehaviorJob(7, 100, other_context),
        ],
        match_id=10,
    )

    assert isinstance(actions[1], WaitAction)
    assert isinstance(actions[7], WaitAction)

    assert worker.get_disabled_behaviors(10) == {100}


def test_disabled_behavior_does_not_affect_other_matches(
    context,
    other_context,
):
    worker = BehaviorWorker()

    definition = BehaviorDefinition(
        id=100,
        code=dedent("""
            def play():
                if self()[0] == 1:
                    raise RuntimeError("Behavior failed")

                return move((1.0, 0.0), 1.0)
            """),
    )

    compiler = BehaviorCompiler()

    worker.register_player_behavior(
        10, 1, 100, compiler.compile(definition)
    )

    worker.register_player_behavior(
        11, 7, 100, compiler.compile(definition)
    )

    worker.execute_batch(
        [BehaviorJob(1, 100, context)],
        match_id=10,
    )

    actions = worker.execute_batch(
        [BehaviorJob(7, 100, other_context)],
        match_id=11,
    )

    assert worker.get_disabled_behaviors(10) == {100}
    assert worker.get_disabled_behaviors(11) == set()

    assert isinstance(actions[7], MoveAction)


def test_voluntary_wait_does_not_disable_behavior(context):
    worker = BehaviorWorker()

    definition = BehaviorDefinition(
        id=100,
        code=dedent("""
            def play():
                return wait()
            """),
    )

    runtime = BehaviorCompiler().compile(definition)

    worker.register_player_behavior(
        10, 1, 100, runtime
    )

    actions = worker.execute_batch(
        [BehaviorJob(1, 100, context)],
        match_id=10,
    )

    assert isinstance(actions[1], WaitAction)
    assert worker.get_disabled_behaviors(10) == set()


def test_invalid_action_disables_behavior(context):
    worker = BehaviorWorker()

    definition = BehaviorDefinition(
        id=100,
        code=dedent("""
            def play():
                return 123
            """),
    )

    runtime = BehaviorCompiler().compile(definition)

    worker.register_player_behavior(
        10, 1, 100, runtime
    )

    actions = worker.execute_batch(
        [BehaviorJob(1, 100, context)],
        match_id=10,
    )

    assert isinstance(actions[1], WaitAction)
    assert worker.get_disabled_behaviors(10) == {100}


def test_release_match_clears_disabled_behaviors():
    worker = BehaviorWorker()

    worker.disable_behavior(10, 100)
    worker.disable_behavior(11, 200)

    worker.release_match(10)

    assert worker.get_disabled_behaviors(10) == set()
    assert worker.get_disabled_behaviors(11) == {200}
