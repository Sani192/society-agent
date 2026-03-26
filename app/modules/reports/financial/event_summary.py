#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jan 23 16:53:43 2026

@author: anonymous
"""

import logging
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.db.models import Payment, Refund, EventExpense, EventContribution
from app.i18n.catalog import translate
from app.utils.logging_helpers import build_log_context, log_service_call
from app.utils.time import utc_now

logger = logging.getLogger(__name__)

class EventFinancialSummaryReport:

    @staticmethod
    @log_service_call(logger, "EventFinancialSummaryReport.generate")
    def generate(db: Session, event_id, *, lang: str | None = None):
        context = build_log_context(event_id=event_id)
        total_paid = (
            db.query(func.coalesce(func.sum(Payment.paid_amount), 0))
            .filter(Payment.event_id == event_id)
            .scalar()
        ) or 0

        total_refund = (
            db.query(func.coalesce(func.sum(Refund.amount), 0))
            .filter(Refund.event_id == event_id)
            .scalar()
        ) or 0

        total_expense = (
            db.query(func.coalesce(func.sum(EventExpense.amount), 0))
            .filter(EventExpense.event_id == event_id)
            .scalar()
        ) or 0

        sponsor_income = (
            db.query(func.coalesce(func.sum(EventContribution.amount), 0))
            .filter(EventContribution.event_id == event_id)
            .scalar()
        ) or 0
        closing_balance = total_paid + sponsor_income - total_expense - total_refund

        generated_at = utc_now().strftime("%d %b %Y %H:%M")
        system_label = translate("report_exports.labels.system", lang)
        rows = [
            [translate("report_exports.labels.rows.income", lang), translate("report_exports.labels.rows.flat_contributions", lang), total_paid, generated_at, system_label],
            [translate("report_exports.labels.rows.income", lang), translate("report_exports.labels.rows.sponsor_contributions", lang), sponsor_income, generated_at, system_label],
            [translate("report_exports.labels.rows.expense", lang), translate("report_exports.labels.rows.total_expenses", lang), total_expense, generated_at, system_label],
            [translate("report_exports.labels.rows.expense", lang), translate("report_exports.labels.rows.refunds", lang), total_refund, generated_at, system_label],
            [translate("report_exports.labels.rows.balance", lang), translate("report_exports.labels.rows.closing_balance", lang), closing_balance, generated_at, system_label],
        ]
        if not rows:
            logger.info(
                "Workflow decision: event financial summary empty | context=%s",
                context
            )
    
        return {
            "header_keys": ["category", "type", "amount", "created_at", "created_by"],
            "headers": [
                translate("report_exports.labels.headers.category", lang),
                translate("report_exports.labels.headers.type", lang),
                translate("report_exports.labels.headers.amount", lang),
                translate("report_exports.labels.headers.created_at", lang),
                translate("report_exports.labels.headers.created_by", lang),
            ],
            "rows": rows
        }
