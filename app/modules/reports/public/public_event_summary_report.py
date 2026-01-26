#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jan 26 11:10:48 2026

@author: anonymous
"""

from sqlalchemy.orm import Session
from app.db.models import (
    Payment,
    EventExpense,
    Refund,
    EventContribution,
    EventFoodPass
)


class PublicEventSummaryReport:

    @staticmethod
    def generate(db: Session, event_id):
        total_income = sum(
            p.paid_amount for p in
            db.query(Payment).filter(Payment.event_id == event_id).all()
        )

        sponsor_income = sum(
            c.amount or 0 for c in
            db.query(EventContribution).filter(EventContribution.event_id == event_id).all()
        )

        total_expenses = sum(
            e.amount for e in
            db.query(EventExpense).filter(EventExpense.event_id == event_id).all()
        )

        refunds = sum(
            r.amount for r in
            db.query(Refund).filter(Refund.event_id == event_id).all()
        )

        participants = db.query(EventFoodPass).filter(
            EventFoodPass.event_id == event_id,
            EventFoodPass.is_participating == True
        ).count()

        sponsors = (
            db.query(EventContribution.source_name)
            .filter(EventContribution.event_id == event_id)
            .distinct()
            .all()
        )

        return {
            "participants": participants,
            "income": total_income + sponsor_income,
            "expenses": total_expenses + refunds,
            "closing_balance": (
                total_income + sponsor_income - total_expenses - refunds
            ),
            "sponsors": [s[0] for s in sponsors]
        }
