#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 25 17:29:05 2026

@author: anonymous
"""

import io
from typing import Any
from reportlab.platypus import SimpleDocTemplate, Spacer
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.styles import getSampleStyleSheet

from app.i18n.catalog import translate
from app.modules.reports.pdf.base import BasePDF, get_pdf_render_language
from app.modules.reports.pdf.formatting import format_report_rows
from app.modules.reports.pdf.table import build_table
from app.utils.time import utc_now


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
        pagesize=landscape(A4),
        rightMargin=40,
        leftMargin=40,
        topMargin=100,
        bottomMargin=60
    )

    getSampleStyleSheet()
    elements: list[Any] = []
    lang = get_pdf_render_language()
    
    # Report Meta
    pdf.report_meta(elements, {
        translate("report_exports.meta.generated_on", lang): utc_now().strftime("%d %b %Y %H:%M"),
        translate("report_exports.meta.currency", lang): "INR (₹)"
    })
    
    # Table
    table_rows = format_report_rows(report["headers"], report["rows"])

    elements.append(build_table(report["headers"], table_rows))

    closing_index = (
        report["headers"].index(translate("report_exports.labels.headers.closing_balance", lang))
        if translate("report_exports.labels.headers.closing_balance", lang) in report["headers"]
        else None
    )
    final_balance = 0
    if report["rows"] and closing_index is not None:
        final_balance = report["rows"][-1][closing_index]

    elements.append(Spacer(1, 18))
    elements.append(
        pdf.summary_box(
            translate("report_exports.labels.summary.current_society_balance", lang),
            [[translate("report_exports.labels.summary.closing_balance", lang), f"₹ {final_balance:,}"]]
        )
    )

    def on_page(canvas, doc):
        pdf.header_footer(canvas, doc.page)

    doc.build(elements, onFirstPage=on_page, onLaterPages=on_page)

    buffer.seek(0)
    return buffer.getvalue()
