#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET


def parse_junit(path: Path) -> dict:
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else root.findall("testsuite")
    total = failures = errors = skipped = 0
    flaky = []
    failed = []

    for suite in suites:
        total += int(suite.attrib.get("tests", 0))
        failures += int(suite.attrib.get("failures", 0))
        errors += int(suite.attrib.get("errors", 0))
        skipped += int(suite.attrib.get("skipped", 0))
        for case in suite.findall("testcase"):
            name = f"{case.attrib.get('classname', '')}::{case.attrib.get('name', '')}".strip(":")
            if case.find("failure") is not None or case.find("error") is not None:
                failed.append(name)
            rerun_nodes = [n for n in list(case) if "rerun" in n.tag.lower() or "flaky" in n.tag.lower()]
            if rerun_nodes:
                flaky.append(name)

    passed = max(total - failures - errors - skipped, 0)
    pass_rate = (passed / total * 100) if total else 0.0
    return {
        "file": str(path),
        "total": total,
        "passed": passed,
        "failed": failures + errors,
        "skipped": skipped,
        "pass_rate": round(pass_rate, 2),
        "flaky_tests": sorted(set(flaky)),
        "failed_tests": failed,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build reliability dashboard payload from junit XML files.")
    parser.add_argument("--junit", nargs="+", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    parser.add_argument("--flaky-threshold", type=int, default=0)
    args = parser.parse_args()

    summaries = [parse_junit(Path(p)) for p in args.junit if Path(p).exists()]
    aggregate_total = sum(s["total"] for s in summaries)
    aggregate_passed = sum(s["passed"] for s in summaries)
    aggregate_failed = sum(s["failed"] for s in summaries)
    aggregate_skipped = sum(s["skipped"] for s in summaries)
    aggregate_flaky = sorted({t for s in summaries for t in s["flaky_tests"]})
    aggregate_pass_rate = round((aggregate_passed / aggregate_total * 100), 2) if aggregate_total else 0.0

    dashboard = {
        "totals": {
            "total": aggregate_total,
            "passed": aggregate_passed,
            "failed": aggregate_failed,
            "skipped": aggregate_skipped,
            "pass_rate": aggregate_pass_rate,
            "flaky_count": len(aggregate_flaky),
        },
        "suites": summaries,
        "flaky_tests": aggregate_flaky,
    }

    Path(args.output_json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output_json).write_text(json.dumps(dashboard, indent=2), encoding="utf-8")

    lines = [
        "# Reliability Dashboard",
        "",
        f"- **Total tests:** {aggregate_total}",
        f"- **Passed:** {aggregate_passed}",
        f"- **Failed:** {aggregate_failed}",
        f"- **Skipped:** {aggregate_skipped}",
        f"- **Pass rate:** {aggregate_pass_rate}%",
        f"- **Flaky candidates:** {len(aggregate_flaky)}",
        "",
        "## Suite breakdown",
        "",
        "| Suite XML | Total | Passed | Failed | Skipped | Pass rate | Flaky |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for s in summaries:
        lines.append(
            f"| `{s['file']}` | {s['total']} | {s['passed']} | {s['failed']} | {s['skipped']} | {s['pass_rate']}% | {len(s['flaky_tests'])} |"
        )

    if aggregate_flaky:
        lines.extend(["", "## Flaky test candidates", ""])
        for test_name in aggregate_flaky:
            lines.append(f"- `{test_name}`")

    Path(args.output_md).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output_md).write_text("\n".join(lines) + "\n", encoding="utf-8")

    if len(aggregate_flaky) > args.flaky_threshold:
        raise SystemExit(
            f"Flaky test threshold exceeded: {len(aggregate_flaky)} > {args.flaky_threshold}."
        )


if __name__ == "__main__":
    main()
