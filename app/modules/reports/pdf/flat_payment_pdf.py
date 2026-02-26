#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jan 23 17:35:10 2026

@author: anonymous
"""

import io
from reportlab.platypus import SimpleDocTemplate, Spacer
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet

from app.modules.reports.pdf.base import BasePDF
from app.modules.reports.pdf.table import build_table
from app.utils.time import utc_now


def generate_flat_payment_pdf(
    *,
    society_name: str,
    event_name: str,
    headers: list,
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
        pagesize=landscape(A4),
        rightMargin=40,
        leftMargin=40,
        topMargin=100,
        bottomMargin=60
    )

    getSampleStyleSheet()
    elements = []

    # Report Meta
    pdf.report_meta(elements, {
        "Event": event_name,
        "Generated On": utc_now().strftime("%d %b %Y %H:%M"),
        "Currency": "INR (₹)"
    })

    # Table
    table = build_table(headers, rows)
    elements.append(table)

    def sum_column(column_name):
        if column_name not in headers:
            return 0
        idx = headers.index(column_name)
        return sum((row[idx] or 0) for row in rows)

    total_expected = sum_column("Expected")
    total_paid = sum_column("Paid")
    total_refunded = sum_column("Refunded")
    total_pending = sum_column("Pending")
    
    elements.append(Spacer(1, 18))
    elements.append(
        pdf.summary_box("Payment Summary", [
            ["Total Expected", f"₹ {total_expected:,}"],
            ["Total Paid", f"₹ {total_paid:,}"],
            ["Total Refunded", f"₹ {total_refunded:,}"],
            ["Total Pending", f"₹ {total_pending:,}"],
        ])
    )

    def on_page(canvas, doc):
        pdf.header_footer(canvas, doc.page)

    doc.build(elements, onFirstPage=on_page, onLaterPages=on_page)

    buffer.seek(0)
    return buffer.getvalue()
