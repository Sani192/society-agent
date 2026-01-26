#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 25 17:27:31 2026

@author: anonymous
"""

from sqlalchemy.orm import Session
from app.db.models import (
    Event,
    SocietyBalance,
    Payment,
    EventExpense,
    Refund,
    EventContribution
)


class BalanceContinuityReport:

    @staticmethod
    def generate(db: Session, society_id):
        events = (
            db.query(Event)
            .filter(Event.society_id == society_id)
            .order_by(Event.event_date.asc())
            .all()
        )

        rows = []
        previous_closing = 0

        for event in events:
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
                closing_balance
            ])

            previous_closing = closing_balance

        return {
            "headers": [
                "Event",
                "Opening Balance",
                "Total Income",
                "Total Expense",
                "Closing Balance"
            ],
            "rows": rows
        }
