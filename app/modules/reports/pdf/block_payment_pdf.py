#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Jan 24 20:25:07 2026

@author: anonymous
"""

import io
from reportlab.platypus import SimpleDocTemplate, Spacer
from reportlab.lib.pagesizes import A4

from app.modules.reports.pdf.base import BasePDF
from app.modules.reports.pdf.table import build_table
from app.utils.time import utc_now


def generate_block_payment_pdf(
    *,
    society_name: str,
    event_name: str,
    headers: list,
    rows: list,
    logo_path: str | None = None
):
    buffer = io.BytesIO()

    pdf = BasePDF(
        buffer=buffer,
        society_name=society_name,
        report_title="Block-wise Payment Report",
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

    elements = []

    # Report meta
    pdf.report_meta(elements, {
        "Event": event_name,
        "Generated On": utc_now().strftime("%d %b %Y %H:%M"),
        "Currency": "INR (₹)"
    })

    # Table
    elements.append(build_table(headers, rows))

    # Summary
    def sum_column(column_name):
        if column_name not in headers:
            return 0
        idx = headers.index(column_name)
        return sum((row[idx] or 0) for row in rows)

    total_expected = sum_column("Expected")
    total_paid = sum_column("Paid")
    total_pending = sum_column("Pending")

    elements.append(Spacer(1, 18))
    elements.append(
        pdf.summary_box("Block-wise Summary", [
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
