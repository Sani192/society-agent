#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Jan 24 20:34:34 2026

@author: anonymous
"""

import io
from datetime import datetime
from reportlab.platypus import SimpleDocTemplate, Spacer, Paragraph
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet

from app.modules.reports.pdf.base import BasePDF
from app.modules.reports.pdf.formatting import format_report_rows
from app.modules.reports.pdf.table import build_table


def generate_event_financial_summary_pdf(
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
        report_title="Event Financial Summary",
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

    # Report meta
    pdf.report_meta(elements, {
        "Event": event_name,
        "Generated On": datetime.now().strftime("%d %b %Y %H:%M"),
        "Currency": "INR (₹)"
    })
    
    # -------------------------------------------------
    # Main summary table (directly from report)
    # -------------------------------------------------
    table_rows = format_report_rows(summary["headers"], summary["rows"])

    elements.append(build_table(summary["headers"], table_rows))

    elements.append(Spacer(1, 18))
    
    # -------------------------------------------------
    # Closing balance highlight box
    # -------------------------------------------------
    amount_index = summary["headers"].index("Amount") if "Amount" in summary["headers"] else 2
    closing_balance = next(
        row[amount_index] for row in summary["rows"]
        if row[0] == "Balance"
    )

    elements.append(
        pdf.summary_box(
            "Closing Balance",
            [["Closing Balance", f"₹ {closing_balance:,}"]]
        )
    )
    
    # -------------------------------------------------
    # Header / footer
    # -------------------------------------------------
    def on_page(canvas, doc):
        pdf.header_footer(canvas, doc.page)

    doc.build(elements, onFirstPage=on_page, onLaterPages=on_page)

    buffer.seek(0)
    return buffer.getvalue()
