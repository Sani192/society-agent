#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jan 23 17:35:10 2026

@author: anonymous
"""

import io
from datetime import datetime
from reportlab.platypus import SimpleDocTemplate, Spacer, Paragraph
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet

from app.modules.reports.pdf.base import BasePDF
from app.modules.reports.pdf.table import build_table


def generate_flat_payment_pdf(
    *,
    society_name: str,
    event_name: str,
    rows: list,
    logo_path: str
):
    buffer = io.BytesIO()

    pdf = BasePDF(
        buffer=buffer,
        society_name=society_name,
        report_title="Flat-wise Payment Report",
        logo_path=logo_path
    )
    
    #page_size = landscape(A4) if len(headers) > 6 else A4

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
    headers = ["Flat", "Block", "Expected", "Paid", "Pending"]
    table = build_table(headers, rows)
    elements.append(table)
    total_expected = sum(r[2] for r in rows)
    total_paid = sum(r[3] for r in rows)
    total_pending = sum(r[4] for r in rows)
    
    elements.append(Spacer(1, 18))
    elements.append(
        pdf.summary_box("Payment Summary", [
            ["Total Expected", f"₹ {total_expected:,}"],
            ["Total Paid", f"₹ {total_paid:,}"],
            ["Total Pending", f"₹ {total_pending:,}"],
        ])
    )

    def on_page(canvas, doc):
        pdf.header_footer(canvas, doc.page)

    doc.build(elements, onFirstPage=on_page, onLaterPages=on_page)

    buffer.seek(0)
    return buffer.getvalue()
