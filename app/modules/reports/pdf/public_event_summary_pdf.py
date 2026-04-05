#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jan 26 11:11:43 2026

@author: anonymous
"""

import io
from typing import Any
from reportlab.platypus import SimpleDocTemplate, Spacer, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4

from app.i18n.catalog import translate
from app.modules.reports.pdf.base import BasePDF, get_pdf_render_language
from app.modules.reports.pdf.formatting import currency_label, format_currency
from app.utils.time import utc_now


def generate_public_event_summary_pdf(
    *,
    society_name: str,
    event_name: str,
    summary: dict,
    logo_path: str | None = None
):
    buffer = io.BytesIO()
    lang = get_pdf_render_language()

    pdf = BasePDF(
        buffer=buffer,
        society_name=society_name,
        report_title=translate("report_exports.pdf_titles.public_summary", lang, event_name=event_name),
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
    elements: list[Any] = []

    pdf.report_meta(elements, {
        translate("report_exports.meta.generated_on", lang): utc_now().strftime("%d %b %Y"),
        translate("report_exports.meta.scope", lang): translate("report_exports.labels.scopes.public_read_only", lang),
        translate("report_exports.meta.currency", lang): currency_label(),
    })

    elements.append(
        pdf.summary_box(translate("report_exports.labels.summary.event_snapshot", lang), [
            [translate("report_exports.labels.summary.participants", lang), summary["participants"]],
            [translate("report_exports.labels.summary.total_income", lang), format_currency(summary["income"])],
            [translate("report_exports.labels.summary.total_expenses", lang), format_currency(summary["expenses"])],
            [translate("report_exports.labels.summary.closing_balance", lang), format_currency(summary["closing_balance"])],
        ])
    )

    if summary["sponsors"]:
        elements.append(Spacer(1, 16))
        elements.append(Paragraph(f"<b>{translate('report_exports.labels.sections.sponsors', lang)}</b>", styles["Heading3"]))
        for s in summary["sponsors"]:
            elements.append(Paragraph(f"• {s}", styles["Normal"]))

    def on_page(canvas, doc):
        pdf.header_footer(canvas, doc.page)

    doc.build(elements, onFirstPage=on_page, onLaterPages=on_page)

    buffer.seek(0)
    return buffer.getvalue()
