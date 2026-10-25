import ast
import inspect

from app.game.behavior_compiler import (
    BehaviorCompilationError,
    BehaviorCompiler,
)
from app.game.models.behavior_definition import BehaviorDefinition


class BehaviorValidationError(Exception):
    """Raised when behavior source code fails validation"""


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


def validate_behavior_code(code: str) -> bool:
    if not isinstance(code, str) or not code.strip():
        raise BehaviorValidationError("El comportamiento no puede estar vacío")

    tree = _parse_syntax(code)
    _validate_ast(tree)
    _validate_module_structure(tree)

    runtime_behavior = _compile_behavior(code)
    _validate_play_signature(runtime_behavior.play)

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

        # Permitir docstrings (strings sueltos como comentarios)
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
