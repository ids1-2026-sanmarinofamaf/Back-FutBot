from textwrap import dedent
import pytest

from app.game.behavior_validator import (
    ALLOWED_COACH_PRIMITIVES,
    ALLOWED_PLAYER_PRIMITIVES,
    BehaviorValidationError,
    validate_behavior_code,
    validate_coach_code,
)
from app.game.default_behaviors import (
    ATTACKER_CODE,
    DEFENDER_CODE,
    MIDFIELDER_CODE,
)


def test_validate_minimal_valid_behavior():
    code = dedent(
        """
        def play():
            return wait()
        """
    )
    assert validate_behavior_code(code) is True


@pytest.mark.parametrize(
    "default_code",
    [ATTACKER_CODE, DEFENDER_CODE, MIDFIELDER_CODE],
)
def test_validate_default_behaviors_are_valid(default_code):
    assert validate_behavior_code(default_code) is True


def test_validate_behavior_with_constants_helpers_and_default_arg():
    code = dedent(
        """
        SPEED = 0.5

        def helper(factor):
            _, my_pos = self()
            ball_pos, _ = ball()
            if distance(my_pos, ball_pos) == 0:
                return wait()
            return move(direction_to(my_pos, ball_pos), factor)

        def play(default_speed=SPEED):
            return helper(default_speed)
        """
    )
    assert validate_behavior_code(code) is True


@pytest.mark.parametrize("empty_code", ["", "   \n\t  "])
def test_validate_fails_when_code_is_empty(empty_code):
    with pytest.raises(
        BehaviorValidationError,
        match="El comportamiento no puede estar vacío",
    ):
        validate_behavior_code(empty_code)


def test_validate_fails_when_code_has_only_comments():
    code = "# solo un comentario\n# otra linea\n"
    with pytest.raises(
        BehaviorValidationError,
        match="El comportamiento debe contener sentencias ejecutables",
    ):
        validate_behavior_code(code)


def test_validate_fails_on_syntax_error():
    code = dedent(
        """
        def play(
            return wait()
        """
    )
    with pytest.raises(BehaviorValidationError, match="Error sintáctico"):
        validate_behavior_code(code)


@pytest.mark.parametrize(
    "import_stmt",
    [
        "import os",
        "from math import sqrt",
    ],
)
def test_validate_fails_when_using_imports(import_stmt):
    code = f"{import_stmt}\ndef play():\n    return wait()\n"
    with pytest.raises(
        BehaviorValidationError,
        match="No se permiten importaciones de librerías",
    ):
        validate_behavior_code(code)


def test_validate_fails_when_using_async_function():
    code = dedent(
        """
        async def play():
            return wait()
        """
    )
    with pytest.raises(
        BehaviorValidationError,
        match="No se permiten funciones asíncronas ni generadores",
    ):
        validate_behavior_code(code)


def test_validate_fails_when_using_yield():
    code = dedent(
        """
        def play():
            yield wait()
            return wait()
        """
    )
    with pytest.raises(
        BehaviorValidationError,
        match="No se permiten funciones asíncronas ni generadores",
    ):
        validate_behavior_code(code)


def test_validate_fails_when_defining_class():
    code = dedent(
        """
        class Helper:
            pass

        def play():
            return wait()
        """
    )
    with pytest.raises(
        BehaviorValidationError,
        match="No se permite la definición de clases",
    ):
        validate_behavior_code(code)


@pytest.mark.parametrize("forbidden", ["eval", "exec", "open", "__import__"])
def test_validate_fails_when_using_forbidden_builtins(forbidden):
    code = dedent(
        f"""
        def play():
            {forbidden}("1")
            return wait()
        """
    )
    with pytest.raises(
        BehaviorValidationError,
        match=f"No se permite el uso de '{forbidden}'",
    ):
        validate_behavior_code(code)


def test_validate_fails_when_accessing_dunder_attribute():
    code = dedent(
        """
        def play():
            x = ().__class__
            return wait()
        """
    )
    with pytest.raises(
        BehaviorValidationError,
        match="No se permite el acceso interno a '__class__'",
    ):
        validate_behavior_code(code)


def test_validate_fails_when_calling_functions_at_top_level():
    code = dedent(
        """
        POS = self()

        def play():
            return wait()
        """
    )
    with pytest.raises(
        BehaviorValidationError,
        match="No se permiten llamadas a funciones fuera de def play",
    ):
        validate_behavior_code(code)


def test_validate_fails_when_top_level_has_loops():
    code = dedent(
        """
        while True:
            pass

        def play():
            return wait()
        """
    )
    with pytest.raises(
        BehaviorValidationError,
        match="En el nivel principal del archivo solo se permiten constantes y definiciones de funciones",
    ):
        validate_behavior_code(code)


def test_validate_fails_when_play_is_missing():
    code = dedent(
        """
        def helper():
            return wait()
        """
    )
    with pytest.raises(
        BehaviorValidationError,
        match="Se debe definir la función principal 'def play\\(\\):'",
    ):
        validate_behavior_code(code)


def test_validate_fails_when_play_has_no_return():
    code = dedent(
        """
        def play():
            x = 1 + 1
        """
    )
    with pytest.raises(
        BehaviorValidationError,
        match="La función play\\(\\) debe retornar una acción",
    ):
        validate_behavior_code(code)


def test_validate_fails_when_play_returns_none():
    code = dedent(
        """
        def play():
            return None
        """
    )
    with pytest.raises(
        BehaviorValidationError,
        match="La función play\\(\\) debe retornar una acción",
    ):
        validate_behavior_code(code)


def test_validate_fails_when_using_undefined_identifier():
    code = dedent(
        """
        def play():
            return waiit()
        """
    )
    with pytest.raises(
        BehaviorValidationError,
        match="El identificador o función 'waiit'.*no está definido",
    ):
        validate_behavior_code(code)


def test_validate_fails_when_play_requires_arguments():
    code = dedent(
        """
        def play(ctx):
            return wait()
        """
    )
    with pytest.raises(
        BehaviorValidationError,
        match="La función play\\(\\) no debe llevar argumentos",
    ):
        validate_behavior_code(code)


def test_validate_fails_when_play_returns_invalid_action_type():
    code = dedent(
        """
        def play():
            return 123
        """
    )
    with pytest.raises(
        BehaviorValidationError,
        match="La función play\\(\\) debe retornar una acción válida",
    ):
        validate_behavior_code(code)


def test_validate_fails_when_play_raises_runtime_error():
    code = dedent(
        """
        def play():
            x = 1 / 0
            return wait()
        """
    )
    with pytest.raises(
        BehaviorValidationError,
        match="Error de ejecución en play\\(\\)",
    ):
        validate_behavior_code(code)


def test_validate_fails_when_primitive_receives_invalid_arguments():
    code = dedent(
        """
        def play():
            return move((0.0, 0.0), 5.0)
        """
    )
    with pytest.raises(
        BehaviorValidationError,
        match="Error de ejecución en play\\(\\)",
    ):
        validate_behavior_code(code)


def test_validate_fails_when_play_has_infinite_loop():
    code = dedent(
        """
        def play():
            while True:
                pass
            return wait()
        """
    )
    with pytest.raises(
        BehaviorValidationError,
        match="El comportamiento excedió el tiempo máximo de ejecución",
    ):
        validate_behavior_code(code)


def test_validate_fails_when_top_level_constant_exceeds_timeout():
    code = dedent(
        """
        HUGE = 9 ** (9 ** 9)

        def play():
            return wait()
        """
    )
    with pytest.raises(
        BehaviorValidationError,
        match="El comportamiento excedió el tiempo máximo de ejecución",
    ):
        validate_behavior_code(code)


# coach (DT) behaviors


def test_coach_and_player_whitelists_follow_their_namespaces():
    assert {"assign", "substitute", "bench", "can_substitute", "trigger"} <= ALLOWED_COACH_PRIMITIVES
    assert not {"move", "kick", "wait", "self"} & ALLOWED_COACH_PRIMITIVES
    assert not {"assign", "substitute"} & ALLOWED_PLAYER_PRIMITIVES


def test_validate_minimal_valid_coach():
    assert validate_coach_code("def coach():\n    return []\n") is True


def test_validate_coach_using_every_coach_primitive():
    code = dedent(
        """
        TARGET = "Attacker"

        def pick_target():
            if TARGET in available_behaviors():
                return TARGET
            return available_behaviors()[0]

        def coach():
            commands = []
            my_goals, their_goals = score()
            if trigger() == CoachTrigger.GOAL_AGAINST and my_goals < their_goals:
                for player_id, _ in teammates():
                    if current_behavior(player_id) != pick_target():
                        commands.append(assign(player_id, pick_target()))
            if can_substitute() and bench():
                commands.append(substitute(teammates()[0][0], bench()[0]))
            return commands
        """
    )
    assert validate_coach_code(code) is True


@pytest.mark.parametrize("empty_code", ["", "   \n"])
def test_validate_coach_fails_when_code_is_empty(empty_code):
    with pytest.raises(BehaviorValidationError, match="no puede estar vacío"):
        validate_coach_code(empty_code)


@pytest.mark.parametrize(
    "code, message",
    [
        ("def play():\n    return wait()\n", "'def coach\\(\\):'"),
        ("def coach():\n    pass\n", "debe retornar una lista"),
        ("def coach():\n    return None\n", "debe retornar una lista"),
        ("def coach(x):\n    return []\n", "no debe llevar argumentos"),
        ("async def coach():\n    return []\n", "asíncronas"),
        ("def coach():\n    yield []\n    return []\n", "generadores"),
        ("def coach():\n    return [wait()]\n", "'wait'"),
        ("def coach():\n    return (assign(1, 'Attacker'),)\n", "debe retornar una lista"),
        ("def coach():\n    return [(1, 2)]\n", "assign\\(...\\) o substitute"),
        ("def coach():\n    return [bench()[5]]\n", "Error de ejecución en coach\\(\\)"),
    ],
)
def test_validate_coach_rejects_invalid_code(code, message):
    with pytest.raises(BehaviorValidationError, match=message):
        validate_coach_code(code)


def test_validate_coach_runs_every_trigger():
    # fails only when a goal is scored against, so a single context is not enough
    code = dedent(
        """
        def coach():
            if trigger() == CoachTrigger.GOAL_AGAINST:
                return 1 / 0
            return []
        """
    )
    with pytest.raises(BehaviorValidationError, match="Error de ejecución en coach"):
        validate_coach_code(code)


def test_validate_coach_times_out_on_infinite_loop():
    code = "def coach():\n    while True:\n        pass\n    return []\n"
    with pytest.raises(BehaviorValidationError, match="tiempo máximo"):
        validate_coach_code(code)


def test_player_validator_rejects_coach_code():
    with pytest.raises(BehaviorValidationError, match="'def play\\(\\):'"):
        validate_behavior_code("def coach():\n    return []\n")
