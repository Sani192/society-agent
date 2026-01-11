#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 11 05:56:22 2026

@author: anonymous
"""

# app/modules/reports/event_summary.py

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.models import (
    Event,
    Payment,
    Refund,
    EventExpense,
    EventContribution,
    SocietyBalance
)


class EventSummaryReport:

    @staticmethod
    def generate(db: Session, *, event_id):
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            raise Exception("Invalid event")

        income_flats = (
            db.query(func.coalesce(func.sum(Payment.paid_amount), 0))
            .filter(Payment.event_id == event_id)
            .scalar()
        )

        income_contributions = (
            db.query(func.coalesce(func.sum(EventContribution.amount), 0))
            .filter(EventContribution.event_id == event_id)
            .scalar()
        )

        expenses = (
            db.query(func.coalesce(func.sum(EventExpense.amount), 0))
            .filter(EventExpense.event_id == event_id)
            .scalar()
        )

        refunds = (
            db.query(func.coalesce(func.sum(Refund.amount), 0))
            .filter(Refund.event_id == event_id)
            .scalar()
        )

        balance = (
            db.query(SocietyBalance)
            .filter(SocietyBalance.event_id == event_id)
            .first()
        )

        return {
            "event": event.name,
            "income": {
                "flats": income_flats,
                "contributions": income_contributions
            },
            "expenses": expenses,
            "refunds": refunds,
            "opening_balance": balance.opening_balance if balance else 0,
            "closing_balance": balance.closing_balance if balance else 0
        }
