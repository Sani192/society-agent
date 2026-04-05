#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Jan 24 20:25:07 2026

@author: anonymous
"""

import io
from typing import Any
from reportlab.platypus import SimpleDocTemplate, Spacer
from reportlab.lib.pagesizes import A4

from app.i18n.catalog import translate
from app.modules.reports.pdf.base import BasePDF, get_pdf_render_language
from app.modules.reports.pdf.formatting import currency_label, format_currency
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

    elements: list[Any] = []
    lang = get_pdf_render_language()

    # Report meta
    pdf.report_meta(elements, {
        translate("report_exports.meta.event", lang): event_name,
        translate("report_exports.meta.generated_on", lang): utc_now().strftime("%d %b %Y %H:%M"),
        translate("report_exports.meta.currency", lang): currency_label()
    })

    # Table
    elements.append(build_table(headers, rows))

    # Summary
    def sum_column(column_name):
        if column_name not in headers:
            return 0
        idx = headers.index(column_name)
        return sum((row[idx] or 0) for row in rows)

    total_expected = sum_column(translate("report_exports.labels.headers.expected", lang))
    total_paid = sum_column(translate("report_exports.labels.headers.paid", lang))
    total_pending = sum_column(translate("report_exports.labels.headers.pending", lang))

    elements.append(Spacer(1, 18))
    elements.append(
        pdf.summary_box(translate("report_exports.labels.summary.block_wise_summary", lang), [
            [translate("report_exports.labels.summary.total_expected", lang), format_currency(total_expected)],
            [translate("report_exports.labels.summary.total_paid", lang), format_currency(total_paid)],
            [translate("report_exports.labels.summary.total_pending", lang), format_currency(total_pending)],
        ])
    )

    def on_page(canvas, doc):
        pdf.header_footer(canvas, doc.page)

    doc.build(elements, onFirstPage=on_page, onLaterPages=on_page)

    buffer.seek(0)
    return buffer.getvalue()
