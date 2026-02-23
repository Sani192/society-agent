#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

REQUIRED_MARKERS = {"integration", "endpoint"}
NAME_HINTS = ("endpoint", "integration", "webhook")


def file_requires_markers(path: Path) -> bool:
    name = path.name
    return name.startswith("test_") and any(hint in name for hint in NAME_HINTS)


def has_required_marker_declaration(text: str) -> bool:
    if "pytestmark" not in text:
        return False
    return any(f"pytest.mark.{marker}" in text for marker in REQUIRED_MARKERS)


def main() -> None:
    missing: list[str] = []
    for path in sorted(Path("tests").glob("test_*.py")):
        if not file_requires_markers(path):
            continue
        text = path.read_text(encoding="utf-8")
        if not has_required_marker_declaration(text):
            missing.append(path.as_posix())

    if missing:
        print("Missing required pytest markers for endpoint/integration-named tests:")
        for file_path in missing:
            print(f"  - {file_path}")
        print(
            "\nAdd a module-level declaration such as:\n"
            "pytestmark = [pytest.mark.integration]\n"
            "or\n"
            "pytestmark = [pytest.mark.integration, pytest.mark.endpoint]"
        )
        raise SystemExit(1)

    print("Marker policy check passed.")


if __name__ == "__main__":
    main()
