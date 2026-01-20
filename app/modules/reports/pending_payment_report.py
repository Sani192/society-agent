#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Jan 17 11:38:47 2026

@author: anonymous
"""

# app/modules/reports/pending_payment_report.py

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.db.models import (
    Event,
    Flat,
    Payment
)


class PendingPaymentReport:

    @staticmethod
    def get_pending_flats(db: Session, *, event_id, society_id):
        """
        Returns flats with pending balance (> 0)
        """
        results = (
            db.query(
                Flat.flat_number,
                Payment.expected_amount,
                Payment.paid_amount
            )
            .join(
                Payment,
                and_(
                    Payment.flat_id == Flat.id,
                    Payment.event_id == event_id
                )
            )
            .filter(
                Flat.society_id == society_id,
                Payment.expected_amount > Payment.paid_amount
            )
            .order_by(Flat.flat_number)
            .all()
        )

        return [
            {
                "flat": r.flat_number,
                "expected": r.expected_amount,
                "paid": r.paid_amount,
                "pending": r.expected_amount - r.paid_amount
            }
            for r in results
        ]
