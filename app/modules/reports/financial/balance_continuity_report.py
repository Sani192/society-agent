#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
from datetime import datetime
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.db.models import (
    Event,
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
    def generate(db: Session, society_id, *, start_date: datetime | None = None, end_date: datetime | None = None):
        context = build_log_context(society_id=society_id)

        payment_sq = (
            db.query(Payment.event_id.label("event_id"), func.coalesce(func.sum(Payment.paid_amount), 0).label("flat_income"))
            .group_by(Payment.event_id)
            .subquery()
        )
        sponsor_sq = (
            db.query(EventContribution.event_id.label("event_id"), func.coalesce(func.sum(EventContribution.amount), 0).label("sponsor_income"))
            .group_by(EventContribution.event_id)
            .subquery()
        )
        expense_sq = (
            db.query(EventExpense.event_id.label("event_id"), func.coalesce(func.sum(EventExpense.amount), 0).label("expenses"))
            .group_by(EventExpense.event_id)
            .subquery()
        )
        refund_sq = (
            db.query(Refund.event_id.label("event_id"), func.coalesce(func.sum(Refund.amount), 0).label("refunds"))
            .group_by(Refund.event_id)
            .subquery()
        )

        query = (
            db.query(
                Event,
                CommitteeMember.name,
                func.coalesce(payment_sq.c.flat_income, 0).label("flat_income"),
                func.coalesce(sponsor_sq.c.sponsor_income, 0).label("sponsor_income"),
                func.coalesce(expense_sq.c.expenses, 0).label("expenses"),
                func.coalesce(refund_sq.c.refunds, 0).label("refunds"),
            )
            .outerjoin(CommitteeMember, CommitteeMember.id == Event.created_by)
            .outerjoin(payment_sq, payment_sq.c.event_id == Event.id)
            .outerjoin(sponsor_sq, sponsor_sq.c.event_id == Event.id)
            .outerjoin(expense_sq, expense_sq.c.event_id == Event.id)
            .outerjoin(refund_sq, refund_sq.c.event_id == Event.id)
            .filter(Event.society_id == society_id)
        )

        if start_date:
            query = query.filter(Event.event_date >= start_date)
        if end_date:
            query = query.filter(Event.event_date <= end_date)

        events = query.order_by(Event.event_date.asc()).all()
        if not events:
            logger.info(
                "Workflow decision: no events found for balance continuity | context=%s",
                context
            )

        rows = []
        previous_closing = 0

        for event, created_by, flat_income, sponsor_income, expenses, refunds in events:
            opening_balance = previous_closing
            closing_balance = opening_balance + flat_income + sponsor_income - expenses - refunds

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
