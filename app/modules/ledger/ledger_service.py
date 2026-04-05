#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 11 05:50:19 2026

@author: anonymous
"""

# app/modules/ledger/ledger_service.py

import logging
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
from app.utils.logging_helpers import build_log_context, log_service_call

logger = logging.getLogger(__name__)


class LedgerService:

    @staticmethod
    @log_service_call(logger, "LedgerService.calculate_event_balance")
    def calculate_event_balance(
        db: Session,
        *,
        event_id,
        opening_balance,
        performed_by,
        override_reason=None
    ):
        context = build_log_context(event_id=event_id, performed_by=performed_by)
        logger.info(
            "Calculating event balance | opening_balance=%s context=%s",
            opening_balance,
            context
        )
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
        logger.info(
            "Computed balances | payments=%s contributions=%s expenses=%s refunds=%s closing_balance=%s context=%s",
            flat_payments,
            contributions,
            expenses,
            refunds,
            closing_balance,
            context
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
            logger.info("Updated existing balance record | context=%s", context)
        else:
            balance = SocietyBalance(
                event_id=event_id,
                opening_balance=opening_balance,
                closing_balance=closing_balance
            )
            db.add(balance)
            logger.info("Created new balance record | context=%s", context)

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
        logger.info("Captured ledger audit log | context=%s", context)

        db.commit()
        logger.info("Committed ledger transaction | context=%s", context)

        return balance
