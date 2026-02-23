#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jan 26 10:29:14 2026

@author: anonymous
"""

import io
from datetime import datetime
from reportlab.platypus import SimpleDocTemplate
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.styles import getSampleStyleSheet

from app.modules.reports.pdf.base import BasePDF
from app.modules.reports.pdf.table import build_table


def generate_governance_audit_pdf(
    *,
    society_name: str,
    report: dict,
    logo_path: str | None = None
):
    buffer = io.BytesIO()

    pdf = BasePDF(
        buffer=buffer,
        society_name=society_name,
        report_title="Governance & Audit Report",
        logo_path=logo_path
    )

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
        "Generated On": datetime.now().strftime("%d %b %Y %H:%M"),
        "Scope": "Overrides, Manual Actions, Report Access"
    })
    
    # Table
    elements.append(
        build_table(report["headers"], report["rows"])
    )

    def on_page(canvas, doc):
        pdf.header_footer(canvas, doc.page)

    doc.build(elements, onFirstPage=on_page, onLaterPages=on_page)

    buffer.seek(0)
    return buffer.getvalue()
