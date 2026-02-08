#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Feb  8 17:23:45 2026

@author: anonymous
"""

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


class LedgerReport:

    @staticmethod
    def generate(db: Session, *, event_id, society_id):
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

        # --------------------------------------------------
        # CLOSING BALANCE
        # --------------------------------------------------
        closing = opening + sum(row[2] for row in ledger)

        ledger.append([
            "Closing Balance",
            "-",
            closing
        ])
        
        return {
            "headers": [
                "Type",
                "Reference",
                "Amount"
            ],
            "rows": ledger
        }
