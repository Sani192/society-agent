#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import io
from typing import Any

from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Spacer

from app.i18n.catalog import translate
from app.modules.reports.pdf.base import BasePDF, get_pdf_render_language
from app.modules.reports.pdf.table import build_table
from app.utils.time import utc_now


def generate_food_pass_operations_pdf(
    *,
    society_name: str,
    event_name: str,
    report: dict,
    logo_path: str | None = None,
):
    buffer = io.BytesIO()

    pdf = BasePDF(
        buffer=buffer,
        society_name=society_name,
        report_title="Food Pass Operations Report",
        logo_path=logo_path,
    )

    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=40,
        leftMargin=40,
        topMargin=100,
        bottomMargin=60,
    )

    elements: list[Any] = []
    summary = report.get("summary", {})
    lang = get_pdf_render_language()

    pdf.report_meta(
        elements,
        {
            translate("report_exports.meta.event", lang): event_name,
            translate("report_exports.meta.generated_on", lang): utc_now().strftime("%d %b %Y %H:%M"),
            translate("report_exports.meta.total_tokens", lang): summary.get("total_passes_generated", 0),
            translate("report_exports.meta.served", lang): summary.get("served_count", 0),
            translate("report_exports.meta.fallback_served", lang): summary.get("fallback_serve_count", 0),
        },
    )

    elements.append(build_table(report["headers"], report["rows"]))
    elements.append(Spacer(1, 18))

    elements.append(
        pdf.summary_box(
            translate("report_exports.labels.summary.food_pass_summary", lang),
            [
                [translate("report_exports.labels.summary.total_tokens_generated", lang), str(summary.get("total_passes_generated", 0))],
                [translate("report_exports.meta.served", lang), str(summary.get("served_count", 0))],
                [translate("report_exports.labels.summary.remaining", lang), str(summary.get("remaining_count", 0))],
                [translate("report_exports.labels.summary.fallback_serves", lang), str(summary.get("fallback_serve_count", 0))],
            ],
        )
    )

    def on_page(canvas, page_doc):
        pdf.header_footer(canvas, page_doc.page)

    doc.build(elements, onFirstPage=on_page, onLaterPages=on_page)

    buffer.seek(0)
    return buffer.getvalue()
