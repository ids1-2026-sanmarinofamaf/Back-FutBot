import pytest

from textwrap import dedent

from app.game.behavior_compiler import (
    BehaviorCompiler,
    BehaviorCompilationError,
)
from app.game.models.behavior_definition import BehaviorDefinition
from app.game.models.runtime_behavior import RuntimeBehavior, RuntimeCoachBehavior
from app.game.types import CoachTrigger
from app.game.models.actions import WaitAction
from app.game.context import set_current_context, clear_current_context


def test_compile_valid_behavior():
    compiler = BehaviorCompiler()

    definition = BehaviorDefinition(
        id=1,
        code=dedent(
            """
            def play():
                return wait()
            """
        ),
    )

    runtime = compiler.compile(definition)

    assert isinstance(runtime, RuntimeBehavior)
    assert runtime.id == 1
    assert callable(runtime.play)


def test_compiled_behavior_can_be_executed(context):
    compiler = BehaviorCompiler()

    definition = BehaviorDefinition(
        id=1,
        code=dedent(
            """
            def play():
                return wait()
            """
        ),
    )

    runtime = compiler.compile(definition)

    set_current_context(context)

    try:
        action = runtime.play()
    finally:
        clear_current_context()

    assert isinstance(action, WaitAction)


def test_compile_behavior_with_helper_function(context):
    compiler = BehaviorCompiler()

    definition = BehaviorDefinition(
        id=1,
        code=dedent(
            """
            def helper():
                return wait()


            def play():
                return helper()
            """
        ),
    )

    runtime = compiler.compile(definition)

    set_current_context(context)

    try:
        action = runtime.play()
    finally:
        clear_current_context()

    assert isinstance(action, WaitAction)


def test_compile_fails_when_play_is_missing():
    compiler = BehaviorCompiler()

    definition = BehaviorDefinition(
        id=1,
        code=(
            """
            def helper():
                return wait()
            """
        ),
    )

    with pytest.raises(BehaviorCompilationError):
        compiler.compile(definition)


def test_compile_fails_when_play_is_not_callable():
    compiler = BehaviorCompiler()

    definition = BehaviorDefinition(
        id=1,
        code=(
        """
        play = 10
        """
        ),
    )

    with pytest.raises(BehaviorCompilationError):
        compiler.compile(definition)


def test_compile_fails_with_invalid_python_code():
    compiler = BehaviorCompiler()

    definition = BehaviorDefinition(
        id=1,
        code=dedent(
            """
            def play(
            return wait()
            """
        ),
    )

    with pytest.raises(BehaviorCompilationError):
        compiler.compile(definition)

def test_compile_valid_coach_behavior():
    compiler = BehaviorCompiler()

    definition = BehaviorDefinition(
        id=1,
        code=dedent(
            """
            def coach():
                return []
            """
        ),
    )

    runtime = compiler.compile(definition, entrypoint="coach")

    assert isinstance(runtime, RuntimeCoachBehavior)
    assert runtime.id == 1
    assert runtime.coach() == []


def test_compile_coach_fails_when_coach_is_missing():
    compiler = BehaviorCompiler()

    definition = BehaviorDefinition(
        id=1,
        code=dedent(
            """
            def play():
                return wait()
            """
        ),
    )

    with pytest.raises(BehaviorCompilationError, match="coach()"):
        compiler.compile(definition, entrypoint="coach")


def test_compile_with_unknown_entrypoint_raises_value_error():
    compiler = BehaviorCompiler()

    definition = BehaviorDefinition(id=1, code="def play():\n    return wait()\n")

    with pytest.raises(ValueError):
        compiler.compile(definition, entrypoint="unknown")


def test_coach_namespace_exposes_coach_trigger_enum():
    compiler = BehaviorCompiler()

    definition = BehaviorDefinition(
        id=1,
        code=dedent(
            """
            def coach():
                return [CoachTrigger.GOAL_FOR]
            """
        ),
    )

    runtime = compiler.compile(definition, entrypoint="coach")

    assert runtime.coach() == [CoachTrigger.GOAL_FOR]


@pytest.mark.parametrize("name", ["assign", "trigger", "current_behavior", "available_behaviors"])
def test_coach_primitives_are_not_available_to_players(name):
    compiler = BehaviorCompiler()

    definition = BehaviorDefinition(
        id=1,
        code=dedent(
            f"""
            def play():
                return {name}
            """
        ),
    )

    runtime = compiler.compile(definition)

    with pytest.raises(NameError):
        runtime.play()


@pytest.mark.parametrize("name", ["move", "kick", "wait", "self"])
def test_player_primitives_are_not_available_to_coaches(name):
    compiler = BehaviorCompiler()

    definition = BehaviorDefinition(
        id=1,
        code=dedent(
            f"""
            def coach():
                return {name}
            """
        ),
    )

    runtime = compiler.compile(definition, entrypoint="coach")

    with pytest.raises(NameError):
        runtime.coach()
