"""
Static validation of coach (DT) behavior code.

The code is only parsed, never executed, so it can be checked inside the
API process without running user code there.
"""

# TODO: temporal hasta que se mergee behavior_validator (SCRUM-136).
# Reemplazar por ese validador parametrizado con entrypoint="coach".


import ast


class CoachCodeError(Exception):
    """Raised when coach behavior code is not accepted."""


MISSING_COACH_MESSAGE = "Code must define a callable coach()."
FORBIDDEN_CODE_MESSAGE = "Code uses a forbidden construction."

# builtins that give access to the system or to the interpreter internals
FORBIDDEN_NAMES: frozenset[str] = frozenset(
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


def validate_coach_code(code: str) -> None:
    """
    Check that coach code defines coach() and uses no forbidden constructions.

    Args:
        code: Source code of the coach behavior.

    Raises:
        CoachCodeError: If the code has a syntax error, does not define
            coach(), runs code at module level or uses imports, forbidden
            builtins or dunder attributes.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as error:
        raise CoachCodeError(MISSING_COACH_MESSAGE) from error

    for statement in tree.body:
        if not _is_allowed_at_module_level(statement):
            raise CoachCodeError(FORBIDDEN_CODE_MESSAGE)

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            raise CoachCodeError(FORBIDDEN_CODE_MESSAGE)

        if isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
            raise CoachCodeError(FORBIDDEN_CODE_MESSAGE)

        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise CoachCodeError(FORBIDDEN_CODE_MESSAGE)

    defines_coach = any(
        isinstance(statement, ast.FunctionDef) and statement.name == "coach"
        for statement in tree.body
    )

    if not defines_coach:
        raise CoachCodeError(MISSING_COACH_MESSAGE)


# only definitions run when the code is loaded: functions, constants and docstrings
def _is_allowed_at_module_level(statement: ast.stmt) -> bool:
    if isinstance(statement, ast.FunctionDef):
        return True

    if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant):
        return True

    if isinstance(statement, (ast.Assign, ast.AnnAssign)):
        return not any(isinstance(node, ast.Call) for node in ast.walk(statement))

    return False
