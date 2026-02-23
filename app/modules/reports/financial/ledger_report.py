#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Feb  8 17:23:45 2026

@author: anonymous
"""

import logging
from sqlalchemy.orm import Session

from app.db.models import (
    Payment,
    Refund,
    EventExpense,
    EventContribution,
    ContributionRefund,
    SocietyBalance,
    Flat,
    CommitteeMember
)
from app.utils.logging_helpers import build_log_context, log_service_call

logger = logging.getLogger(__name__)

def format_timestamp(value):
    return value.strftime("%d %b %Y %H:%M") if value else "-"


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
            opening,
            "-",
            "System"
        ])

        # --------------------------------------------------
        # MEMBER PAYMENTS
        # --------------------------------------------------
        payments = (
            db.query(
                Flat.flat_number,
                Payment.paid_amount,
                Payment.paid_at
            )
            .join(Flat, Flat.id == Payment.flat_id)
            .filter(Payment.event_id == event_id)
            .all()
        )

        for flat, amount, paid_at in payments:
            ledger.append([
                "Member Payment",
                f"Flat {flat}",
                amount,
                format_timestamp(paid_at),
                "System"
            ])

        # --------------------------------------------------
        # SPONSOR CONTRIBUTIONS (CASH)
        # --------------------------------------------------
        sponsors = (
            db.query(
                EventContribution.source_name,
                EventContribution.amount,
                EventContribution.created_at
            )
            .filter(
                EventContribution.event_id == event_id,
                EventContribution.amount.isnot(None)
            )
            .all()
        )

        for name, amount, created_at in sponsors:
            ledger.append([
                "Sponsor Contribution",
                name,
                amount,
                format_timestamp(created_at),
                "System"
            ])

        # --------------------------------------------------
        # MEMBER REFUNDS
        # --------------------------------------------------
        refunds = (
            db.query(
                Flat.flat_number,
                Refund.amount,
                Refund.created_at,
                CommitteeMember.name
            )
            .join(Flat, Flat.id == Refund.flat_id)
            .outerjoin(CommitteeMember, CommitteeMember.id == Refund.created_by)
            .filter(
                Refund.event_id == event_id,
                Refund.status.in_(["approved", "refunded"])
            )
            .all()
        )

        for flat, amount, created_at, created_by in refunds:
            ledger.append([
                "Member Refund",
                f"Flat {flat}",
                -amount,
                format_timestamp(created_at),
                created_by or "System"
            ])

        # --------------------------------------------------
        # SPONSOR REFUNDS
        # --------------------------------------------------
        sponsor_refunds = (
            db.query(
                EventContribution.source_name,
                ContributionRefund.amount,
                ContributionRefund.processed_at
            )
            .join(
                ContributionRefund,
                ContributionRefund.contribution_id == EventContribution.id
            )
            .filter(EventContribution.event_id == event_id)
            .all()
        )

        for name, amount, processed_at in sponsor_refunds:
            ledger.append([
                "Sponsor Refund",
                name,
                -amount,
                format_timestamp(processed_at),
                "System"
            ])

        # --------------------------------------------------
        # EXPENSES
        # --------------------------------------------------
        expenses = (
            db.query(
                EventExpense.description,
                EventExpense.amount,
                EventExpense.created_at
            )
            .filter(EventExpense.event_id == event_id)
            .all()
        )

        for desc, amount, created_at in expenses:
            ledger.append([
                "Expense",
                desc,
                -amount,
                format_timestamp(created_at),
                "System"
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
            closing,
            "-",
            "System"
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
                "Amount",
                "Created At",
                "Created By"
            ],
            "rows": ledger
        }
