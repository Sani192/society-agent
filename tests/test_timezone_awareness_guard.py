import ast
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1] / "app"


def _datetime_bindings(tree: ast.AST) -> tuple[set[str], set[str]]:
    """Return symbol names bound to datetime class and datetime module."""
    datetime_class_names: set[str] = set()
    datetime_module_names: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "datetime":
            for alias in node.names:
                bound_name = alias.asname or alias.name
                if alias.name == "datetime":
                    datetime_class_names.add(bound_name)
                if alias.name == "timezone":
                    # timezone imports are allowed and ignored here
                    continue

        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "datetime":
                    datetime_module_names.add(alias.asname or alias.name)

    # Common unaliased names
    datetime_class_names.add("datetime")
    datetime_module_names.add("datetime")

    return datetime_class_names, datetime_module_names


def _naive_datetime_violations(source: str) -> list[tuple[int, str]]:
    violations: list[tuple[int, str]] = []
    tree = ast.parse(source)
    datetime_class_names, datetime_module_names = _datetime_bindings(tree)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue

        owner = node.func.value
        attr = node.func.attr

        # Case 1: from datetime import datetime as dt; dt.utcnow() / dt.now()
        if isinstance(owner, ast.Name) and owner.id in datetime_class_names:
            if attr == "utcnow":
                violations.append((node.lineno, "datetime.utcnow() is forbidden; use utc_now()"))
                continue
            if attr == "now" and not node.args and not node.keywords:
                violations.append((node.lineno, "datetime.now() without timezone is forbidden; use utc_now()"))
                continue

        # Case 2: import datetime as dt; dt.datetime.utcnow() / dt.datetime.now()
        if isinstance(owner, ast.Attribute):
            base = owner.value
            if (
                isinstance(base, ast.Name)
                and base.id in datetime_module_names
                and owner.attr == "datetime"
            ):
                if attr == "utcnow":
                    violations.append((node.lineno, "datetime.utcnow() is forbidden; use utc_now()"))
                    continue
                if attr == "now" and not node.args and not node.keywords:
                    violations.append((node.lineno, "datetime.now() without timezone is forbidden; use utc_now()"))

    return violations


def test_app_code_uses_timezone_aware_datetimes() -> None:
    violations: list[str] = []

    for path in APP_ROOT.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        for line_no, message in _naive_datetime_violations(source):
            rel = path.relative_to(APP_ROOT.parent)
            violations.append(f"{rel}:{line_no} - {message}")

    assert not violations, "\n".join(violations)
