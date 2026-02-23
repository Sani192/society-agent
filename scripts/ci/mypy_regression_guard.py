#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def _extract_errors(text: str) -> set[str]:
    return {
        line.strip()
        for line in text.splitlines()
        if ": error:" in line
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Fail CI when mypy introduces new errors beyond baseline.")
    parser.add_argument("--baseline", default="ci/mypy-baseline.txt")
    parser.add_argument("targets", nargs="*", default=["app", "scripts"])
    args = parser.parse_args()

    baseline_path = Path(args.baseline)
    baseline_errors = {
        line.strip() for line in baseline_path.read_text(encoding="utf-8").splitlines() if line.strip()
    } if baseline_path.exists() else set()

    cmd = [
        "mypy",
        *args.targets,
        "--ignore-missing-imports",
        "--show-error-codes",
        "--hide-error-context",
        "--no-pretty",
        "--no-color-output",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    output = (proc.stdout or "") + (proc.stderr or "")
    current_errors = _extract_errors(output)

    new_errors = sorted(current_errors - baseline_errors)
    resolved_errors = sorted(baseline_errors - current_errors)

    print(f"Baseline errors: {len(baseline_errors)}")
    print(f"Current errors: {len(current_errors)}")
    print(f"New errors: {len(new_errors)}")
    print(f"Resolved errors: {len(resolved_errors)}")

    if resolved_errors:
        print("\nResolved errors (please prune baseline):")
        for line in resolved_errors:
            print(f"  - {line}")

    if new_errors:
        print("\nNew mypy errors introduced:")
        for line in new_errors:
            print(f"  - {line}")
        raise SystemExit(1)

    # Preserve normal mypy failure if there are errors but no baseline file.
    if proc.returncode != 0 and not baseline_errors:
        print("\nMypy returned errors and no baseline exists.")
        print(output)
        raise SystemExit(proc.returncode)


if __name__ == "__main__":
    main()
