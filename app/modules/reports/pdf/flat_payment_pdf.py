#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jan 23 17:35:10 2026

@author: anonymous
"""

import io
from typing import Any
from reportlab.platypus import SimpleDocTemplate, Spacer
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet

from app.i18n.catalog import translate
from app.modules.reports.pdf.base import BasePDF, get_pdf_render_language
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
    elements: list[Any] = []
    lang = get_pdf_render_language()

    # Report Meta
    pdf.report_meta(elements, {
        translate("report_exports.meta.event", lang): event_name,
        translate("report_exports.meta.generated_on", lang): utc_now().strftime("%d %b %Y %H:%M"),
        translate("report_exports.meta.currency", lang): "INR (₹)"
    })

    # Table
    table = build_table(headers, rows)
    elements.append(table)

    def sum_column(column_name):
        if column_name not in headers:
            return 0
        idx = headers.index(column_name)
        return sum((row[idx] or 0) for row in rows)

    total_expected = sum_column(translate("report_exports.labels.headers.expected", lang))
    total_paid = sum_column(translate("report_exports.labels.headers.paid", lang))
    total_refunded = sum_column(translate("report_exports.labels.headers.refunded", lang))
    total_pending = sum_column(translate("report_exports.labels.headers.pending", lang))
    
    elements.append(Spacer(1, 18))
    elements.append(
        pdf.summary_box(translate("report_exports.labels.summary.payment_summary", lang), [
            [translate("report_exports.labels.summary.total_expected", lang), f"₹ {total_expected:,}"],
            [translate("report_exports.labels.summary.total_paid", lang), f"₹ {total_paid:,}"],
            [translate("report_exports.labels.summary.total_refunded", lang), f"₹ {total_refunded:,}"],
            [translate("report_exports.labels.summary.total_pending", lang), f"₹ {total_pending:,}"],
        ])
    )

    def on_page(canvas, doc):
        pdf.header_footer(canvas, doc.page)

    doc.build(elements, onFirstPage=on_page, onLaterPages=on_page)

    buffer.seek(0)
    return buffer.getvalue()
