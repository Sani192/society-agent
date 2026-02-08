#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jan 23 16:53:43 2026

@author: anonymous
"""

import logging
from sqlalchemy.orm import Session
from app.db.models import Payment, Refund, EventExpense, EventContribution
from app.utils.logging_helpers import build_log_context, log_service_call

logger = logging.getLogger(__name__)

class EventFinancialSummaryReport:

    @staticmethod
    @log_service_call(logger, "EventFinancialSummaryReport.generate")
    def generate(db: Session, event_id):
        context = build_log_context(event_id=event_id)
        paid = db.query(Payment).filter(
            Payment.event_id == event_id
        ).with_entities(Payment.paid_amount).all()

        refunds = db.query(Refund).filter(
            Refund.event_id == event_id
        ).with_entities(Refund.amount).all()

        expenses = db.query(EventExpense).filter(
            EventExpense.event_id == event_id
        ).with_entities(EventExpense.amount).all()

        contributions = db.query(EventContribution).filter(
            EventContribution.event_id == event_id
        ).with_entities(EventContribution.amount).all()

        total_paid = sum(x[0] for x in paid)
        total_refund = sum(x[0] for x in refunds)
        total_expense = sum(x[0] for x in expenses)
        sponsor_income = sum(x[0] for x in contributions if x[0])
        closing_balance = total_paid + sponsor_income - total_expense - total_refund

        rows = [
            ["Income", "Flat Contributions", total_paid],
            ["Income", "Sponsor Contributions", sponsor_income],
            ["Expense", "Total Expenses", total_expense],
            ["Expense", "Refunds", total_refund],
            ["Balance", "Closing Balance", closing_balance],
        ]
        if not rows:
            logger.info(
                "Workflow decision: event financial summary empty | context=%s",
                context
            )
    
        return {
            "headers": ["Category", "Type", "Amount"],
            "rows": rows
        }
