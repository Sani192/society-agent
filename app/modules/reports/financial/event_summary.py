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
from app.utils.logging_helpers import build_log_context, log_service_call
from app.utils.time import utc_now

logger = logging.getLogger(__name__)

class EventFinancialSummaryReport:

    @staticmethod
    @log_service_call(logger, "EventFinancialSummaryReport.generate")
    def generate(db: Session, event_id):
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
        rows = [
            ["Income", "Flat Contributions", total_paid, generated_at, "System"],
            ["Income", "Sponsor Contributions", sponsor_income, generated_at, "System"],
            ["Expense", "Total Expenses", total_expense, generated_at, "System"],
            ["Expense", "Refunds", total_refund, generated_at, "System"],
            ["Balance", "Closing Balance", closing_balance, generated_at, "System"],
        ]
        if not rows:
            logger.info(
                "Workflow decision: event financial summary empty | context=%s",
                context
            )
    
        return {
            "headers": ["Category", "Type", "Amount", "Created At", "Created By"],
            "rows": rows
        }
