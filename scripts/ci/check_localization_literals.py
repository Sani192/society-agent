#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from pathlib import Path
import re

TARGET_GLOBS = (
    "app/handlers/shared/*.py",
    "app/channels/whatsapp/ui_router.py",
    "app/channels/core/handler.py",
)
BASELINE_PATH = Path("scripts/ci/localization_literal_guard_baseline.txt")

MESSAGE_BUILDERS = {"join_lines", "format_heading", "build_invalid_command_response"}
INTERNAL_LITERAL_VALUES = {
    "rows",
    "title",
    "id",
    "description",
    "format",
    "category",
    "report",
    "filename",
    "expected",
    "paid",
    "refunded",
    "balance",
    "flat_number",
    "total_passes",
    "served",
    "remaining",
    "fallback_served",
    "total_plates",
    "served_plates",
    "remaining_plates",
    "name",
    "veg",
    "jain",
    "kids",
    "net_paid",
}
LOCALIZATION_KEY_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$")
INTERNAL_TOKEN_RE = re.compile(r"^[a-z0-9_:-]+(?:\:\:[a-z0-9_:-]+)*$")


@dataclass(frozen=True)
class Violation:
    file_path: str
    lineno: int
    call_name: str
    literal: str

    def serialize(self) -> str:
        text = self.literal.replace("\\", "\\\\").replace("\n", "\\n")
        return f"{self.file_path}:{self.lineno}:{self.call_name}:{text}"


def _iter_target_files() -> list[Path]:
    files: list[Path] = []
    for pattern in TARGET_GLOBS:
        candidate = Path(pattern)
        if candidate.is_absolute():
            if candidate.is_file():
                files.append(candidate)
            continue
        files.extend(Path().glob(pattern))
    return sorted({path for path in files if path.is_file()})


def _call_name(func: ast.AST) -> str:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _is_relevant_call(name: str) -> bool:
    return name.startswith("send_") or name.endswith("_response") or name in MESSAGE_BUILDERS


def _build_parent_map(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    parents: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    return parents


def _has_ancestor_translate_call(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> bool:
    cursor = parents.get(node)
    while cursor is not None:
        if isinstance(cursor, ast.Call) and _call_name(cursor.func) == "translate":
            return True
        cursor = parents.get(cursor)
    return False


def _is_user_facing_literal(value: str) -> bool:
    stripped = value.strip()
    if not stripped:
        return False
    if stripped in INTERNAL_LITERAL_VALUES:
        return False
    if LOCALIZATION_KEY_RE.match(stripped):
        return False
    if INTERNAL_TOKEN_RE.match(stripped):
        return False
    if not any(ch.isalpha() for ch in stripped):
        return False
    return True


def collect_violations() -> list[Violation]:
    violations: list[Violation] = []
    seen_literals: set[tuple[str, int, str]] = set()
    for file_path in _iter_target_files():
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        parents = _build_parent_map(tree)

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue

            call_name = _call_name(node.func)
            if not _is_relevant_call(call_name):
                continue

            scan_nodes: list[ast.AST] = [*node.args, *(kw.value for kw in node.keywords)]
            for scan_node in scan_nodes:
                for child in ast.walk(scan_node):
                    if not isinstance(child, ast.Constant) or not isinstance(child.value, str):
                        continue
                    if _has_ancestor_translate_call(child, parents):
                        continue
                    if not _is_user_facing_literal(child.value):
                        continue
                    dedupe_key = (file_path.as_posix(), child.lineno, child.value)
                    if dedupe_key in seen_literals:
                        continue
                    seen_literals.add(dedupe_key)
                    violations.append(
                        Violation(
                            file_path=file_path.as_posix(),
                            lineno=child.lineno,
                            call_name=call_name,
                            literal=child.value,
                        )
                    )

    violations.sort(key=lambda item: (item.file_path, item.lineno, item.call_name, item.literal))
    return violations


def _read_baseline(path: Path) -> set[str]:
    if not path.exists():
        return set()
    lines = [line.rstrip("\n") for line in path.read_text(encoding="utf-8").splitlines()]
    return {line for line in lines if line and not line.lstrip().startswith("#")}


def _write_baseline(path: Path, entries: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    output = [
        "# Baseline allowlist for scripts/ci/check_localization_literals.py",
        "# Format: path:line:call_name:literal",
        *entries,
    ]
    path.write_text("\n".join(output) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Guard against hard-coded user-facing literals in response calls.")
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="Regenerate baseline from current violations.",
    )
    args = parser.parse_args()

    violations = collect_violations()
    serialized = [violation.serialize() for violation in violations]

    if args.update_baseline:
        _write_baseline(BASELINE_PATH, serialized)
        print(f"Updated baseline with {len(serialized)} entries at {BASELINE_PATH}.")
        return

    baseline = _read_baseline(BASELINE_PATH)
    current = set(serialized)
    new_violations = sorted(current - baseline)

    if new_violations:
        print("Found new direct user-facing literals in response/message calls:")
        for item in new_violations:
            print(f"  - {item}")
        print("\nUse translate('...') keys (or localized text dictionary lookups) for user-visible content.")
        raise SystemExit(1)

    print("Localization literal guard passed.")


if __name__ == "__main__":
    main()
