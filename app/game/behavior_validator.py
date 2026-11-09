"""
Behavior source code validation utilities.

This module provides static AST analysis, compilation checks, and isolated
subprocess dry-run execution to verify that user-submitted behavior code is
safe and conforms to the Behavior API contract before execution or storage.
"""

import ast
import inspect

import multiprocessing as mp
from multiprocessing.queues import Queue
from queue import Empty

from app.game.behavior_compiler import (
    BehaviorCompilationError,
    BehaviorCompiler,
)
from app.game.behavior_executor import _is_assignment
from app.game.context import (
    BehaviorContext,
    CoachContext,
    clear_current_context,
    set_current_context,
)
from app.game.models.actions import KickAction, MoveAction, WaitAction
from app.game.models.behavior_definition import BehaviorDefinition
from app.game.types import CoachTrigger, Period, Side, Substitution


class BehaviorValidationError(Exception):
    """Raised when behavior source code fails any validation stage."""


DRY_RUN_TIMEOUT_SECONDS: float = 2.0

FORBIDDEN_BUILTINS: frozenset[str] = frozenset(
    {
        "__import__",
        "breakpoint",
        "compile",
        "delattr",
        "eval",
        "exec",
        "getattr",
        "globals",
        "input",
        "locals",
        "open",
        "setattr",
        "vars",
    }
)

SAFE_BUILTINS: frozenset[str] = frozenset(
    {
        "abs",
        "all",
        "any",
        "bool",
        "dict",
        "enumerate",
        "float",
        "int",
        "len",
        "list",
        "max",
        "min",
        "range",
        "round",
        "set",
        "sorted",
        "str",
        "sum",
        "tuple",
        "zip",
        "True",
        "False",
        "None",
    }
)
# the whitelist of each entrypoint is exactly what its namespace exposes
_compiler = BehaviorCompiler()
ALLOWED_PLAYER_PRIMITIVES: frozenset[str] = frozenset(
    _compiler._build_player_namespace().keys()
)
ALLOWED_COACH_PRIMITIVES: frozenset[str] = frozenset(
    _compiler._build_coach_namespace().keys()
)
# kept for backwards compatibility: the player whitelist
ALLOWED_PRIMITIVES: frozenset[str] = ALLOWED_PLAYER_PRIMITIVES

_ALLOWED_PRIMITIVES_BY_ENTRYPOINT: dict[str, frozenset[str]] = {
    "play": ALLOWED_PLAYER_PRIMITIVES,
    "coach": ALLOWED_COACH_PRIMITIVES,
}

# message used when the entrypoint has no return with a value
_MISSING_RETURN_MESSAGES: dict[str, str] = {
    "play": "La función play() debe retornar una acción (move, kick o wait)",
    "coach": "La función coach() debe retornar una lista de assign(...) y/o substitute(...)",
}


def validate_behavior_code(code: str) -> bool:
    """
    Validate player behavior Python source code.

    Verifies that the code is non-empty and runs the complete validation
    pipeline inside an isolated worker process with a strict timeout: syntax
    parsing, AST security checks, module structure rules, identifier
    whitelisting, compilation, play() signature inspection, and dry-run
    execution.

    Args:
        code: Raw Python source code defining the behavior.

    Returns:
        True if the behavior code passes all validation stages.

    Raises:
        BehaviorValidationError: If the code is empty, syntactically invalid,
            uses forbidden constructs/identifiers, fails to compile, or fails
            or times out during validation in the worker process.
    """
    if not isinstance(code, str) or not code.strip():
        raise BehaviorValidationError("El comportamiento no puede estar vacío")

    _run_validation_in_worker(code, entrypoint="play")

    return True


def validate_coach_code(code: str) -> bool:
    """
    Validate coach (DT) behavior Python source code.

    Runs the same pipeline as validate_behavior_code, with coach() as the
    entrypoint: the coach primitives as whitelist, and a dry-run of coach()
    against sample CoachContext scenarios. coach() must return a list whose
    elements are built with assign(...) or substitute(...); an empty list
    is valid.

    Args:
        code: Raw Python source code defining the coach behavior.

    Returns:
        True if the coach code passes all validation stages.

    Raises:
        BehaviorValidationError: If the code is empty or fails any stage.
    """
    if not isinstance(code, str) or not code.strip():
        raise BehaviorValidationError("El comportamiento no puede estar vacío")

    _run_validation_in_worker(code, entrypoint="coach")

    return True


def _parse_syntax(code: str) -> ast.Module:
    """
    Parse behavior source code into an AST module and verify it is non-empty.

    Args:
        code: Raw Python source code string.

    Returns:
        Parsed AST module node.

    Raises:
        BehaviorValidationError: If the source code contains syntax errors or
            has no executable statements (e.g., comments only).
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        line_info = f" en la línea {exc.lineno}" if exc.lineno else ""
        raise BehaviorValidationError(
            f"Error sintáctico{line_info}: {exc.msg}"
        ) from exc

    if not tree.body:
        raise BehaviorValidationError(
            "El comportamiento debe contener sentencias ejecutables"
        )
    return tree


def _validate_ast(tree: ast.AST) -> None:
    """
    Inspect the AST for forbidden language constructs and unsafe builtins.

    Blocks imports, async/generator constructs, class definitions, forbidden
    builtins, and dunder attribute access.

    Args:
        tree: Parsed AST of the behavior code.

    Raises:
        BehaviorValidationError: If any disallowed AST node or attribute access
            is detected.
    """
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            raise BehaviorValidationError(
                "No se permiten importaciones de librerías en el comportamiento"
            )

        if isinstance(node, (ast.AsyncFunctionDef, ast.Await, ast.Yield, ast.YieldFrom)):
            raise BehaviorValidationError(
                "No se permiten funciones asíncronas ni generadores (yield/async)"
            )

        if isinstance(node, ast.ClassDef):
            raise BehaviorValidationError(
                "No se permite la definición de clases en el comportamiento"
            )

        if isinstance(node, ast.Name) and node.id in FORBIDDEN_BUILTINS:
            raise BehaviorValidationError(
                f"No se permite el uso de '{node.id}' en el comportamiento"
            )

        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise BehaviorValidationError(
                f"No se permite el acceso interno a '{node.attr}'"
            )


def _validate_module_structure(tree: ast.Module, entrypoint: str = "play") -> None:
    """
    Validate top-level module statements and the presence of a valid play() function.

    Top-level statements are restricted to function definitions, constant
    assignments without function calls, and module docstrings. Ensures that
    play() is defined and contains at least one non-None return statement.

    Args:
        tree: Parsed AST module node.

    Raises:
        BehaviorValidationError: If disallowed top-level statements exist,
            play() is missing, or play() never returns a value.
    """
    entry_node: ast.FunctionDef | None = None

    for stmt in tree.body:
        if isinstance(stmt, ast.FunctionDef):
            if stmt.name == entrypoint:
                entry_node = stmt
            continue

        if isinstance(stmt, (ast.Assign, ast.AnnAssign)):
            if any(isinstance(sub, ast.Call) for sub in ast.walk(stmt)):
                raise BehaviorValidationError(
                    f"No se permiten llamadas a funciones fuera de def {entrypoint}() o funciones auxiliares"
                )
            continue

        if (
            isinstance(stmt, ast.Expr)
            and isinstance(stmt.value, ast.Constant)
            and isinstance(stmt.value.value, str)
        ):
            continue

        raise BehaviorValidationError(
            "En el nivel principal del archivo solo se permiten constantes y definiciones de funciones (def)"
        )

    if entry_node is None:
        raise BehaviorValidationError(
            f"Se debe definir la función principal 'def {entrypoint}():'"
        )

    has_value_return = any(
        isinstance(node, ast.Return)
        and node.value is not None
        and not (isinstance(node.value, ast.Constant) and node.value.value is None)
        for node in ast.walk(entry_node)
    )

    if not has_value_return:
        raise BehaviorValidationError(_MISSING_RETURN_MESSAGES[entrypoint])


def _collect_defined_names(tree: ast.AST) -> set[str]:
    """
    Collect all user-defined identifier names declared in the AST.

    Includes function names, function parameters, and variables assigned via
    store contexts (assignments, loop targets, comprehensions).

    Args:
        tree: Parsed AST of the behavior code.

    Returns:
        Set of identifier names defined within the user's code.
    """
    defined: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            defined.add(node.name)
            for arg in node.args.posonlyargs + node.args.args + node.args.kwonlyargs:
                defined.add(arg.arg)
            if node.args.vararg:
                defined.add(node.args.vararg.arg)
            if node.args.kwarg:
                defined.add(node.args.kwarg.arg)

        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            defined.add(node.id)

    return defined


def _validate_identifiers(
    tree: ast.AST,
    allowed_primitives: frozenset[str] = ALLOWED_PLAYER_PRIMITIVES,
) -> None:
    """
    Verify that all loaded identifiers belong to the allowed whitelist.

    Allowed identifiers consist of Behavior API primitives, safe Python
    builtins, and names defined within the behavior code itself.

    Args:
        tree: Parsed AST of the behavior code.

    Raises:
        BehaviorValidationError: If an unknown or unauthorized identifier is
            referenced.
    """
    user_defined = _collect_defined_names(tree)
    allowed_names = allowed_primitives | SAFE_BUILTINS | user_defined

    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            if node.id not in allowed_names:
                line_info = f" (línea {node.lineno})" if hasattr(node, "lineno") else ""
                raise BehaviorValidationError(
                    f"El identificador o función '{node.id}'{line_info} no está definido en el comportamiento ni en la Behavior API"
                )


def _compile_behavior(code: str, entrypoint: str = "play"):
    """
    Compile behavior source code using BehaviorCompiler.

    Args:
        code: Raw Python source code string.

    Returns:
        Compiled RuntimeBehavior instance.

    Raises:
        BehaviorValidationError: If compilation fails or play() is not callable.
    """
    compiler = BehaviorCompiler()
    definition = BehaviorDefinition(id=0, code=code)

    try:
        return compiler.compile(definition, entrypoint=entrypoint)
    except BehaviorCompilationError as exc:
        cause = exc.__cause__
        if cause is not None:
            raise BehaviorValidationError(
                f"Error al compilar el código: {cause}"
            ) from exc
        raise BehaviorValidationError(
            f"Se debe definir correctamente la función {entrypoint}()"
        ) from exc


def _validate_entrypoint_signature(entry_fn, entrypoint: str = "play") -> None:
    """
    Verify that the compiled entrypoint function (play() or coach()) requires
    no positional or keyword arguments.

    Args:
        entry_fn: Callable entrypoint extracted from the compiled behavior.
        entrypoint: Name of the entrypoint, used in the error message.

    Raises:
        BehaviorValidationError: If the entrypoint defines required parameters.
    """
    signature = inspect.signature(entry_fn)
    required_params = [
        param
        for param in signature.parameters.values()
        if param.default is inspect.Parameter.empty
        and param.kind
        in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        )
    ]

    if required_params:
        raise BehaviorValidationError(
            f"La función {entrypoint}() no debe llevar argumentos"
        )


def _validate_play_signature(play_fn) -> None:
    """Kept for backwards compatibility; see _validate_entrypoint_signature."""
    _validate_entrypoint_signature(play_fn, "play")


def _build_sample_contexts() -> list[BehaviorContext]:
    """
    Build synthetic BehaviorContext scenarios for dry-run validation.

    Provides two representative game states: one where the ball is far from the
    player and one where the ball is within the player's control range.

    Returns:
        List of sample BehaviorContext instances.
    """
    # Escenario 1: Pelota lejos del jugador
    far_ball_ctx = BehaviorContext(
        player=(1, (10.0, 10.0)),
        teammates=[(2, (15.0, 5.0)), (3, (15.0, 15.0))],
        opponents=[(4, (25.0, 5.0)), (5, (25.0, 10.0)), (6, (25.0, 15.0))],
        ball=((20.0, 10.0), (0.0, 0.0)),
        my_team_score=0,
        opponent_score=0,
        starting_position=(10.0, 10.0),
        current_period=Period.FIRST_QUARTER,
        side=Side.LEFT,
        match_time_remaining=120.0,
        period_time_remaining=30.0,
        control_range=1.0,
        tics_until_kick=0,
        max_move_speed=5.0,
        max_kick_force=15.0,
    )

    # Escenario 2: Pelota bajo control del jugador (can_kick() == True)
    near_ball_ctx = BehaviorContext(
        player=(1, (20.0, 10.0)),
        teammates=[(2, (25.0, 5.0)), (3, (25.0, 15.0))],
        opponents=[(4, (30.0, 5.0)), (5, (30.0, 10.0)), (6, (30.0, 15.0))],
        ball=((20.5, 10.0), (0.0, 0.0)),
        my_team_score=0,
        opponent_score=0,
        starting_position=(20.0, 10.0),
        current_period=Period.FIRST_QUARTER,
        side=Side.LEFT,
        match_time_remaining=120.0,
        period_time_remaining=30.0,
        control_range=1.0,
        tics_until_kick=0,
        max_move_speed=5.0,
        max_kick_force=15.0,
    )

    return [far_ball_ctx, near_ball_ctx]


def _build_sample_coach_contexts() -> list[CoachContext]:
    """
    Build synthetic CoachContext scenarios for dry-run validation.

    Covers every trigger, and both a context where a substitution can be
    requested and one where it cannot (last quarter), since coach code
    usually branches on trigger() and can_substitute().

    Returns:
        List of sample CoachContext instances.
    """
    def build(
        trigger: CoachTrigger,
        my_team_score: int,
        opponent_score: int,
        current_period: Period,
        can_substitute: bool,
    ) -> CoachContext:
        return CoachContext(
            teammates=[(1, (10.0, 10.0)), (2, (15.0, 5.0)), (3, (15.0, 15.0))],
            opponents=[(4, (25.0, 5.0)), (5, (25.0, 10.0)), (6, (25.0, 15.0))],
            ball=((20.0, 10.0), (0.0, 0.0)),
            my_team_score=my_team_score,
            opponent_score=opponent_score,
            current_period=current_period,
            side=Side.LEFT,
            match_time_remaining=120.0,
            period_time_remaining=30.0,
            trigger=trigger,
            available_behaviors=["Attacker", "Defender", "Midfielder"],
            current_behaviors={1: "Defender", 2: "Midfielder", 3: "Attacker"},
            bench=[7, 8, 9],
            can_substitute=can_substitute,
        )

    return [
        build(CoachTrigger.PERIOD_START, 0, 0, Period.FIRST_QUARTER, True),
        build(CoachTrigger.GOAL_FOR, 1, 0, Period.SECOND_QUARTER, True),
        build(CoachTrigger.GOAL_AGAINST, 1, 1, Period.THIRD_QUARTER, False),
        build(CoachTrigger.PERIOD_START, 1, 2, Period.FOURTH_QUARTER, False),
    ]


def _run_play_dry_run(runtime_behavior) -> None:
    """
    Execute play() against each sample BehaviorContext and check the action.

    Raises:
        BehaviorValidationError: If play() raises or returns an invalid action.
    """
    for context in _build_sample_contexts():
        set_current_context(context)
        try:
            action = runtime_behavior.play()
        except Exception as exc:
            raise BehaviorValidationError(
                f"Error de ejecución en play(): {exc}"
            ) from exc
        finally:
            clear_current_context()

        if not isinstance(action, (MoveAction, KickAction, WaitAction)):
            raise BehaviorValidationError(
                "La función play() debe retornar una acción válida: move(), kick() o wait()"
            )


def _run_coach_dry_run(runtime_coach) -> None:
    """
    Execute coach() against each sample CoachContext and check the result.

    The result must be a list (possibly empty) whose elements were built with
    assign(...) or substitute(...). During a match invalid elements are just
    discarded; here they are rejected so the user finds the mistake early.

    Raises:
        BehaviorValidationError: If coach() raises or returns an invalid value.
    """
    for context in _build_sample_coach_contexts():
        set_current_context(context)
        try:
            commands = runtime_coach.coach()
        except Exception as exc:
            raise BehaviorValidationError(
                f"Error de ejecución en coach(): {exc}"
            ) from exc
        finally:
            clear_current_context()

        if not isinstance(commands, list):
            raise BehaviorValidationError(
                "La función coach() debe retornar una lista de assign(...) y/o substitute(...)"
            )

        for command in commands:
            if not (_is_assignment(command) or isinstance(command, Substitution)):
                raise BehaviorValidationError(
                    "Cada elemento de la lista que retorna coach() debe "
                    "construirse con assign(...) o substitute(...)"
                )


def _validation_worker(code: str, output_queue: Queue, entrypoint: str = "play") -> None:
    """
    Worker target executed in a separate process to validate behavior code.

    Runs static AST checks, compiles the behavior once, validates the
    entrypoint signature, and executes the entrypoint (play() or coach())
    against each sample context, sending None to output_queue on success or
    an error message string on failure.

    Args:
        code: Raw Python source code string to validate, compile, and execute.
        output_queue: Multiprocessing queue used to report the validation result.
        entrypoint: "play" for player behaviors, "coach" for coach behaviors.
    """
    try:
        tree = _parse_syntax(code)
        _validate_ast(tree)
        _validate_module_structure(tree, entrypoint)
        _validate_identifiers(tree, _ALLOWED_PRIMITIVES_BY_ENTRYPOINT[entrypoint])

        runtime_behavior = _compile_behavior(code, entrypoint)
        _validate_entrypoint_signature(getattr(runtime_behavior, entrypoint), entrypoint)

        if entrypoint == "coach":
            _run_coach_dry_run(runtime_behavior)
        else:
            _run_play_dry_run(runtime_behavior)

        output_queue.put(None)
    except BehaviorValidationError as exc:
        output_queue.put(str(exc))
    except Exception as exc:
        output_queue.put(f"Error al validar la ejecución del comportamiento: {exc}")


def _run_validation_in_worker(code: str, entrypoint: str = "play") -> None:
    """
    Execute the complete validation pipeline in an isolated child process with a strict timeout.

    Terminates the child process if validation exceeds DRY_RUN_TIMEOUT_SECONDS
    and ensures IPC queue resources are always released.

    Args:
        code: Raw Python source code string to validate.

    Raises:
        BehaviorValidationError: If validation times out, fails static/compilation
            checks, raises a runtime exception, or returns an invalid action.
    """
    context = mp.get_context("forkserver")
    output_queue: Queue = context.Queue()
    process = context.Process(
        target=_validation_worker,
        args=(code, output_queue, entrypoint),
    )

    process.start()

    try:
        error_message = output_queue.get(timeout=DRY_RUN_TIMEOUT_SECONDS)
    except Empty as exc:
        process.terminate()
        process.join()
        raise BehaviorValidationError(
            "El comportamiento excedió el tiempo máximo de ejecución (posible bucle infinito)"
        ) from exc
    finally:
        output_queue.close()
        output_queue.join_thread()

    process.join()

    if error_message is not None:
        raise BehaviorValidationError(error_message)
