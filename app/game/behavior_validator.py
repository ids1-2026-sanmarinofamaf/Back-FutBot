"""
Behavior source code validation utilities.

This module provides static AST analysis, compilation checks, and isolated
subprocess dry-run execution to verify that user-submitted behavior code is
safe and conforms to the Behavior API contract before execution or storage.
"""

import ast
import inspect
from multiprocessing import Process, Queue
from queue import Empty

from app.game.behavior_compiler import (
    BehaviorCompilationError,
    BehaviorCompiler,
)
from app.game.context import (
    BehaviorContext,
    clear_current_context,
    set_current_context,
)
from app.game.models.actions import KickAction, MoveAction, WaitAction
from app.game.models.behavior_definition import BehaviorDefinition
from app.game.types import Period, Side


class BehaviorValidationError(Exception):
    """Raised when behavior source code fails any validation stage."""


DRY_RUN_TIMEOUT_SECONDS: float = 0.5

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

ALLOWED_PRIMITIVES: frozenset[str] = frozenset(
    BehaviorCompiler()._build_namespace().keys()
)


def validate_behavior_code(code: str) -> bool:
    """
    Validate player behavior Python source code.

    Runs the complete validation pipeline: syntax parsing, AST security
    checks, module structure rules, identifier whitelisting, compilation,
    play() signature inspection, and an isolated dry-run execution.

    Args:
        code: Raw Python source code defining the behavior.

    Returns:
        True if the behavior code passes all validation stages.

    Raises:
        BehaviorValidationError: If the code is empty, syntactically invalid,
            uses forbidden constructs/identifiers, fails to compile, or fails
            during dry-run execution.
    """
    if not isinstance(code, str) or not code.strip():
        raise BehaviorValidationError("El comportamiento no puede estar vacío")

    tree = _parse_syntax(code)
    _validate_ast(tree)
    _validate_module_structure(tree)
    _validate_identifiers(tree)

    runtime_behavior = _compile_behavior(code)
    _validate_play_signature(runtime_behavior.play)
    _dry_run_behavior(code)

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


def _validate_module_structure(tree: ast.Module) -> None:
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
    play_node: ast.FunctionDef | None = None

    for stmt in tree.body:
        if isinstance(stmt, ast.FunctionDef):
            if stmt.name == "play":
                play_node = stmt
            continue

        if isinstance(stmt, (ast.Assign, ast.AnnAssign)):
            if any(isinstance(sub, ast.Call) for sub in ast.walk(stmt)):
                raise BehaviorValidationError(
                    "No se permiten llamadas a funciones fuera de def play() o funciones auxiliares"
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

    if play_node is None:
        raise BehaviorValidationError(
            "Se debe definir la función principal 'def play():'"
        )

    has_value_return = any(
        isinstance(node, ast.Return)
        and node.value is not None
        and not (isinstance(node.value, ast.Constant) and node.value.value is None)
        for node in ast.walk(play_node)
    )

    if not has_value_return:
        raise BehaviorValidationError(
            "La función play() debe retornar una acción (move, kick o wait)"
        )


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


def _validate_identifiers(tree: ast.AST) -> None:
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
    allowed_names = ALLOWED_PRIMITIVES | SAFE_BUILTINS | user_defined

    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            if node.id not in allowed_names:
                line_info = f" (línea {node.lineno})" if hasattr(node, "lineno") else ""
                raise BehaviorValidationError(
                    f"El identificador o función '{node.id}'{line_info} no está definido en el comportamiento ni en la Behavior API"
                )


def _compile_behavior(code: str):
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
        return compiler.compile(definition)
    except BehaviorCompilationError as exc:
        cause = exc.__cause__
        if cause is not None:
            raise BehaviorValidationError(
                f"Error al compilar el código: {cause}"
            ) from exc
        raise BehaviorValidationError(
            "Se debe definir correctamente la función play()"
        ) from exc


def _validate_play_signature(play_fn) -> None:
    """
    Verify that the compiled play() function requires no positional or keyword arguments.

    Args:
        play_fn: Callable play function extracted from the compiled behavior.

    Raises:
        BehaviorValidationError: If play() defines any required parameters.
    """
    signature = inspect.signature(play_fn)
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
            "La función play() no debe llevar argumentos"
        )


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


def _dry_run_worker(code: str, output_queue: Queue) -> None:
    """
    Worker target executed in a separate process to test behavior execution.

    Compiles the behavior and executes play() against each sample context,
    sending None to output_queue on success or an error message string on
    failure.

    Args:
        code: Raw Python source code string to compile and execute.
        output_queue: Multiprocessing queue used to report the validation result.
    """
    try:
        runtime_behavior = BehaviorCompiler().compile(
            BehaviorDefinition(id=0, code=code)
        )

        for context in _build_sample_contexts():
            set_current_context(context)
            try:
                action = runtime_behavior.play()
            except Exception as exc:
                output_queue.put(f"Error de ejecución en play(): {exc}")
                return
            finally:
                clear_current_context()

            if not isinstance(action, (MoveAction, KickAction, WaitAction)):
                output_queue.put(
                    "La función play() debe retornar una acción válida: move(), kick() o wait()"
                )
                return

        output_queue.put(None)
    except Exception as exc:
        output_queue.put(f"Error al validar la ejecución del comportamiento: {exc}")


def _dry_run_behavior(code: str) -> None:
    """
    Execute the behavior in an isolated child process with a strict timeout.

    Terminates the child process if execution exceeds DRY_RUN_TIMEOUT_SECONDS
    and ensures IPC queue resources are always released.

    Args:
        code: Raw Python source code string to dry-run.

    Raises:
        BehaviorValidationError: If execution times out, raises a runtime
            exception, or returns an object that is not a valid game action.
    """
    output_queue: Queue = Queue()
    process = Process(
        target=_dry_run_worker,
        args=(code, output_queue),
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
