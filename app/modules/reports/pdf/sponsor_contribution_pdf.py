#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 25 16:28:17 2026

@author: anonymous
"""

import io
from reportlab.platypus import SimpleDocTemplate, Spacer
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.styles import getSampleStyleSheet

from app.i18n.catalog import translate
from app.modules.reports.pdf.base import BasePDF, get_pdf_render_language
from app.modules.reports.pdf.formatting import format_report_rows
from app.modules.reports.pdf.table import build_table
from app.utils.time import utc_now


def generate_sponsor_contribution_pdf(
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
        report_title="Sponsor & Contribution Report",
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
    lang = get_pdf_render_language()

    # Report Meta
    pdf.report_meta(elements, {
        translate("report_exports.meta.event", lang): event_name,
        translate("report_exports.meta.generated_on", lang): utc_now().strftime("%d %b %Y %H:%M"),
        translate("report_exports.meta.currency", lang): "INR (₹)"
    })
    
    # Table
    elements.append(
        build_table(
            report["headers"],
            format_report_rows(report["headers"], report["rows"])
        )
    )
    elements.append(Spacer(1, 18))
    elements.append(
        pdf.summary_box(
            translate("report_exports.labels.summary.total_cash_sponsorship", lang),
            [[translate("report_exports.labels.summary.total_cash", lang), f"₹ {report['total_cash']:,}"]]
        )
    )

    def on_page(canvas, doc):
        pdf.header_footer(canvas, doc.page)

    doc.build(elements, onFirstPage=on_page, onLaterPages=on_page)

    buffer.seek(0)
    return buffer.getvalue()
