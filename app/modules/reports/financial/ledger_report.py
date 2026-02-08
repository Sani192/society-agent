#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Feb  8 17:23:45 2026

@author: anonymous
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.models import (
    Payment,
    Refund,
    EventExpense,
    EventContribution,
    ContributionRefund,
    SocietyBalance,
    Flat
)
from app.utils.logging_helpers import build_log_context, log_service_call

logger = logging.getLogger(__name__)


class LedgerReport:

    @staticmethod
    @log_service_call(logger, "LedgerReport.generate")
    def generate(db: Session, *, event_id, society_id):
        context = build_log_context(event_id=event_id, society_id=society_id)
        ledger = []

        # --------------------------------------------------
        # OPENING BALANCE
        # --------------------------------------------------
        opening = (
            db.query(SocietyBalance.opening_balance)
            .filter(
                SocietyBalance.event_id == event_id,
                SocietyBalance.society_id == society_id
            )
            .scalar()
        ) or 0

        ledger.append([
            "Opening Balance",
            "-",
            opening
        ])

        # --------------------------------------------------
        # MEMBER PAYMENTS
        # --------------------------------------------------
        payments = (
            db.query(
                Flat.flat_number,
                Payment.paid_amount
            )
            .join(Flat, Flat.id == Payment.flat_id)
            .filter(Payment.event_id == event_id)
            .all()
        )

        for flat, amount in payments:
            ledger.append([
                "Member Payment",
                f"Flat {flat}",
                amount
            ])

        # --------------------------------------------------
        # SPONSOR CONTRIBUTIONS (CASH)
        # --------------------------------------------------
        sponsors = (
            db.query(
                EventContribution.source_name,
                EventContribution.amount
            )
            .filter(
                EventContribution.event_id == event_id,
                EventContribution.amount.isnot(None)
            )
            .all()
        )

        for name, amount in sponsors:
            ledger.append([
                "Sponsor Contribution",
                name,
                amount
            ])

        # --------------------------------------------------
        # MEMBER REFUNDS
        # --------------------------------------------------
        refunds = (
            db.query(
                Flat.flat_number,
                Refund.amount
            )
            .join(Flat, Flat.id == Refund.flat_id)
            .filter(
                Refund.event_id == event_id,
                Refund.status.in_(["approved", "refunded"])
            )
            .all()
        )

        for flat, amount in refunds:
            ledger.append([
                "Member Refund",
                f"Flat {flat}",
                -amount
            ])

        # --------------------------------------------------
        # SPONSOR REFUNDS
        # --------------------------------------------------
        sponsor_refunds = (
            db.query(
                EventContribution.source_name,
                ContributionRefund.amount
            )
            .join(
                ContributionRefund,
                ContributionRefund.contribution_id == EventContribution.id
            )
            .filter(EventContribution.event_id == event_id)
            .all()
        )

        for name, amount in sponsor_refunds:
            ledger.append([
                "Sponsor Refund",
                name,
                -amount
            ])

        # --------------------------------------------------
        # EXPENSES
        # --------------------------------------------------
        expenses = (
            db.query(
                EventExpense.description,
                EventExpense.amount
            )
            .filter(EventExpense.event_id == event_id)
            .all()
        )

        for desc, amount in expenses:
            ledger.append([
                "Expense",
                desc,
                -amount
            ])
        if len(ledger) <= 1:
            logger.info(
                "Workflow decision: ledger has only opening entries | context=%s",
                context
            )

        # --------------------------------------------------
        # CLOSING BALANCE
        # --------------------------------------------------
        closing = opening + sum(row[2] for row in ledger)

        ledger.append([
            "Closing Balance",
            "-",
            closing
        ])
        if len(ledger) <= 2:
            logger.info(
                "Workflow decision: ledger has no transaction rows | context=%s",
                context
            )
        
        return {
            "headers": [
                "Type",
                "Reference",
                "Amount"
            ],
            "rows": ledger
        }
