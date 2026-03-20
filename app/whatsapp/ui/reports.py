from __future__ import annotations

from app.i18n.catalog import translate


def reports_intro(*, lang: str | None = None) -> str:
    return translate("reports.intro", lang)


def build_reports_sections(*, is_committee: bool, lang: str | None = None) -> list[dict]:
    rows = [
        {
            "id": "summary",
            "title": translate("reports.summary.title", lang),
            "description": translate("reports.summary.description", lang),
        },
        {
            "id": "block report",
            "title": translate("reports.block_report.title", lang),
            "description": translate("reports.block_report.description", lang),
        },
        {
            "id": "report options",
            "title": translate("reports.report_options.title", lang),
            "description": translate("reports.report_options.description", lang),
        },
    ]
    if is_committee:
        rows.append(
            {
                "id": "participation report",
                "title": translate("reports.participation_report.title", lang),
                "description": translate("reports.participation_report.description", lang),
            }
        )

    return [{"title": translate("reports.section_title", lang), "rows": rows}]
