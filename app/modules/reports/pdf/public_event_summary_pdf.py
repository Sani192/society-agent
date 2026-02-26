#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jan 26 11:11:43 2026

@author: anonymous
"""

import io
from reportlab.platypus import SimpleDocTemplate, Spacer, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4

from app.modules.reports.pdf.base import BasePDF
from app.utils.time import utc_now


def generate_public_event_summary_pdf(
    *,
    society_name: str,
    event_name: str,
    summary: dict,
    logo_path: str | None = None
):
    buffer = io.BytesIO()

    pdf = BasePDF(
        buffer=buffer,
        society_name=society_name,
        report_title=f"{event_name} – Public Summary",
        logo_path=logo_path
    )

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=100,
        bottomMargin=60
    )

    styles = getSampleStyleSheet()
    elements = []

    pdf.report_meta(elements, {
        "Generated On": utc_now().strftime("%d %b %Y"),
        "Scope": "Public • Read-only"
    })

    elements.append(
        pdf.summary_box("Event Snapshot", [
            ["Participants", summary["participants"]],
            ["Total Income", f"₹ {summary['income']:,}"],
            ["Total Expenses", f"₹ {summary['expenses']:,}"],
            ["Closing Balance", f"₹ {summary['closing_balance']:,}"],
        ])
    )

    if summary["sponsors"]:
        elements.append(Spacer(1, 16))
        elements.append(Paragraph("<b>Sponsors</b>", styles["Heading3"]))
        for s in summary["sponsors"]:
            elements.append(Paragraph(f"• {s}", styles["Normal"]))

    def on_page(canvas, doc):
        pdf.header_footer(canvas, doc.page)

    doc.build(elements, onFirstPage=on_page, onLaterPages=on_page)

    buffer.seek(0)
    return buffer.getvalue()
