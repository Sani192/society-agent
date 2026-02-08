#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 25 17:27:31 2026

@author: anonymous
"""

import logging
from sqlalchemy.orm import Session
from app.db.models import (
    Event,
    SocietyBalance,
    Payment,
    EventExpense,
    Refund,
    EventContribution,
    CommitteeMember
)
from app.utils.logging_helpers import build_log_context, log_service_call

logger = logging.getLogger(__name__)

def format_timestamp(value):
    return value.strftime("%d %b %Y %H:%M") if value else "-"


class BalanceContinuityReport:

    @staticmethod
    @log_service_call(logger, "BalanceContinuityReport.generate")
    def generate(db: Session, society_id):
        context = build_log_context(society_id=society_id)
        events = (
            db.query(Event, CommitteeMember.name)
            .outerjoin(
                CommitteeMember,
                CommitteeMember.id == Event.created_by
            )
            .filter(Event.society_id == society_id)
            .order_by(Event.event_date.asc())
            .all()
        )
        if not events:
            logger.info(
                "Workflow decision: no events found for balance continuity | context=%s",
                context
            )

        rows = []
        previous_closing = 0

        for event, created_by in events:
            # income
            flat_income = sum(
                p.paid_amount for p in
                db.query(Payment).filter(Payment.event_id == event.id).all()
            )

            sponsor_income = sum(
                c.amount or 0 for c in
                db.query(EventContribution).filter(EventContribution.event_id == event.id).all()
            )

            # expenses
            expenses = sum(
                e.amount for e in
                db.query(EventExpense).filter(EventExpense.event_id == event.id).all()
            )

            refunds = sum(
                r.amount for r in
                db.query(Refund).filter(Refund.event_id == event.id).all()
            )

            opening_balance = previous_closing
            closing_balance = (
                opening_balance +
                flat_income +
                sponsor_income -
                expenses -
                refunds
            )

            rows.append([
                event.name,
                opening_balance,
                flat_income + sponsor_income,
                expenses + refunds,
                closing_balance,
                format_timestamp(event.created_at),
                created_by or "System"
            ])

            previous_closing = closing_balance

        if not rows:
            logger.info(
                "Workflow decision: balance continuity report empty | context=%s",
                context
            )
        return {
            "headers": [
                "Event",
                "Opening Balance",
                "Total Income",
                "Total Expense",
                "Closing Balance",
                "Created At",
                "Created By"
            ],
            "rows": rows
        }
