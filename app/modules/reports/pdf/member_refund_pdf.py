#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Feb  8 17:01:29 2026

@author: anonymous
"""

import io
from datetime import datetime
from reportlab.platypus import SimpleDocTemplate, Spacer
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.styles import getSampleStyleSheet

from app.modules.reports.pdf.base import BasePDF
from app.modules.reports.pdf.formatting import format_report_rows
from app.modules.reports.pdf.table import build_table


def generate_member_refund_pdf(
    *,
    society_name: str,
    event_name: str,
    report: dict,
    logo_path: str | None = None
):
    buffer = io.BytesIO()

    pdf = BasePDF(
        buffer=buffer,
        society_name=society_name,
        report_title="Member Refunds Report",
        logo_path=logo_path
    )

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * 28,
        leftMargin=2 * 28,
        topMargin=4 * 28,
        bottomMargin=3 * 28,
    )

    styles = getSampleStyleSheet()
    elements = []

    # Report Meta
    pdf.report_meta(elements, {
        "Event": event_name,
        "Generated On": datetime.now().strftime("%d %b %Y %H:%M"),
        "Currency": "INR (₹)"
    })
    
    # Table
    elements.append(
        build_table(
            report["headers"],
            format_report_rows(report["headers"], report["rows"])
        )
    )

    elements.append(Spacer(1, 18))

    def on_page(canvas, doc):
        pdf.header_footer(canvas, doc.page)

    doc.build(elements, onFirstPage=on_page, onLaterPages=on_page)

    buffer.seek(0)
    return buffer.getvalue()
