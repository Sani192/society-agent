#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Jan 24 20:25:07 2026

@author: anonymous
"""

import io
from datetime import datetime
from reportlab.platypus import SimpleDocTemplate, Spacer
from reportlab.lib.pagesizes import A4

from app.modules.reports.pdf.base import BasePDF
from app.modules.reports.pdf.table import build_table


def generate_block_payment_pdf(
    *,
    society_name: str,
    event_name: str,
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
        "Generated On": datetime.now().strftime("%d %b %Y %H:%M"),
        "Currency": "INR (₹)"
    })

    # Table
    headers = ["Block", "Expected", "Paid", "Pending"]
    elements.append(build_table(headers, rows))

    # Summary
    total_expected = sum(r[1] for r in rows)
    total_paid = sum(r[2] for r in rows)
    total_pending = sum(r[3] for r in rows)

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
