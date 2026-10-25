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
    """Raised when behavior source code fails validation"""


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
