from __future__ import annotations


def reports_intro() -> str:
    return "Select a report to export. PDF is default."


def build_reports_sections(*, is_committee: bool) -> list[dict]:
    rows = [
        {"id": "summary", "title": "Summary", "description": "Overall event summary"},
        {"id": "block report", "title": "Block Report", "description": "Building-wise breakdown"},
        {"id": "report options", "title": "Report Options", "description": "Browse exportable reports"},
    ]
    if is_committee:
        rows.append(
            {
                "id": "participation report",
                "title": "Participation Report",
                "description": "Committee analytics report",
            }
        )

    return [{"title": "Reports", "rows": rows}]
