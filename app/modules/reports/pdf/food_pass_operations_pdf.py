#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import io

from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Spacer

from app.modules.reports.pdf.base import BasePDF
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

    elements = []
    summary = report.get("summary", {})

    pdf.report_meta(
        elements,
        {
            "Event": event_name,
            "Generated On": utc_now().strftime("%d %b %Y %H:%M"),
            "Total Tokens": summary.get("total_passes_generated", 0),
            "Served": summary.get("served_count", 0),
            "Fallback Served": summary.get("fallback_serve_count", 0),
        },
    )

    elements.append(build_table(report["headers"], report["rows"]))
    elements.append(Spacer(1, 18))

    elements.append(
        pdf.summary_box(
            "Food Pass Summary",
            [
                ["Total Tokens Generated", str(summary.get("total_passes_generated", 0))],
                ["Served", str(summary.get("served_count", 0))],
                ["Remaining", str(summary.get("remaining_count", 0))],
                ["Fallback Serves", str(summary.get("fallback_serve_count", 0))],
            ],
        )
    )

    def on_page(canvas, page_doc):
        pdf.header_footer(canvas, page_doc.page)

    doc.build(elements, onFirstPage=on_page, onLaterPages=on_page)

    buffer.seek(0)
    return buffer.getvalue()
