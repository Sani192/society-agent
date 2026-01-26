#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 25 17:29:05 2026

@author: anonymous
"""

import io
from datetime import datetime
from reportlab.platypus import SimpleDocTemplate, Spacer
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet

from app.modules.reports.pdf.base import BasePDF
from app.modules.reports.pdf.table import build_table


def generate_balance_continuity_pdf(
    *,
    society_name: str,
    report: dict,
    logo_path: str | None = None
):
    buffer = io.BytesIO()

    pdf = BasePDF(
        buffer=buffer,
        society_name=society_name,
        report_title="Balance Carry-Forward Report",
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
    
    # Report Meta
    pdf.report_meta(elements, {
        "Generated On": datetime.now().strftime("%d %b %Y %H:%M"),
        "Currency": "INR (₹)"
    })
    
    # Table
    table_rows = [
        [
            r[0],
            f"₹ {r[1]:,}",
            f"₹ {r[2]:,}",
            f"₹ {r[3]:,}",
            f"₹ {r[4]:,}",
        ]
        for r in report["rows"]
    ]

    elements.append(
        build_table(report["headers"], table_rows)
    )

    final_balance = report["rows"][-1][4] if report["rows"] else 0

    elements.append(Spacer(1, 18))
    elements.append(
        pdf.summary_box(
            "Current Society Balance",
            [["Closing Balance", f"₹ {final_balance:,}"]]
        )
    )

    def on_page(canvas, doc):
        pdf.header_footer(canvas, doc.page)

    doc.build(elements, onFirstPage=on_page, onLaterPages=on_page)

    buffer.seek(0)
    return buffer.getvalue()
