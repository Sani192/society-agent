#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 11 05:50:19 2026

@author: anonymous
"""

# app/modules/ledger/ledger_service.py

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.models import (
    Event,
    Payment,
    Refund,
    EventContribution,
    EventExpense,
    SocietyBalance,
    AuditLog
)


class LedgerService:

    @staticmethod
    def calculate_event_balance(
        db: Session,
        *,
        event_id,
        opening_balance,
        performed_by,
        override_reason=None
    ):
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            raise Exception("Invalid event")

        # ---- INCOME ----

        flat_payments = (
            db.query(func.coalesce(func.sum(Payment.paid_amount), 0))
            .filter(Payment.event_id == event_id)
            .scalar()
        )

        contributions = (
            db.query(func.coalesce(func.sum(EventContribution.amount), 0))
            .filter(EventContribution.event_id == event_id)
            .scalar()
        )

        # ---- EXPENSES ----

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

        # ---- CALCULATION ----

        closing_balance = (
            opening_balance
            + flat_payments
            + contributions
            - expenses
            - refunds
        )

        # ---- UPSERT SOCIETY BALANCE ----

        balance = (
            db.query(SocietyBalance)
            .filter(SocietyBalance.event_id == event_id)
            .first()
        )

        if balance:
            balance.opening_balance = opening_balance
            balance.closing_balance = closing_balance
        else:
            balance = SocietyBalance(
                society_id=event.society_id,
                event_id=event_id,
                opening_balance=opening_balance,
                closing_balance=closing_balance
            )
            db.add(balance)

        db.add(AuditLog(
            society_id=event.society_id,
            entity_type="ledger",
            entity_id=event_id,
            action="CALCULATE_BALANCE",
            reason=(
                f"OVERRIDE: {override_reason}"
                if override_reason
                else "Normal ledger calculation"
            ),
            performed_by=performed_by
        ))

        db.commit()

        return balance
