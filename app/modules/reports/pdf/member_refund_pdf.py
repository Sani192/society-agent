#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Feb  8 17:01:29 2026

@author: anonymous
"""

import io
from typing import Any
from reportlab.platypus import SimpleDocTemplate, Spacer
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet

from app.i18n.catalog import translate
from app.modules.reports.pdf.base import BasePDF, get_pdf_render_language
from app.modules.reports.pdf.formatting import currency_label, format_report_rows
from app.modules.reports.pdf.table import build_table
from app.utils.time import utc_now


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

    getSampleStyleSheet()
    elements: list[Any] = []
    lang = get_pdf_render_language()

    # Report Meta
    pdf.report_meta(elements, {
        translate("report_exports.meta.event", lang): event_name,
        translate("report_exports.meta.generated_on", lang): utc_now().strftime("%d %b %Y %H:%M"),
        translate("report_exports.meta.currency", lang): currency_label()
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
