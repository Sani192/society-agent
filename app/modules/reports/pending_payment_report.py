#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Jan 17 11:38:47 2026

@author: anonymous
"""

# app/modules/reports/pending_payment_report.py

from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from app.db.models import (
    Flat,
    Payment,
    EventFoodPass,
    Refund
)


class PendingPaymentReport:

    @staticmethod
    def get_pending_flats(db: Session, *, event_id, society_id):
        """
        Returns flats with pending balance (> 0)
        """
        results = (
            db.query(
                Flat.flat_number.label("flat_number"),
                EventFoodPass.total_amount.label("expected_amount"),
                func.coalesce(Payment.paid_amount, 0).label("paid_amount"),
                func.coalesce(func.sum(Refund.amount), 0).label("refunded_amount")
            )
            .join(
                EventFoodPass,
                and_(
                    EventFoodPass.flat_id == Flat.id,
                    EventFoodPass.event_id == event_id,
                    EventFoodPass.is_participating.is_(True)
                )
            )
            .outerjoin(
                Payment,
                and_(
                    Payment.flat_id == Flat.id,
                    Payment.event_id == event_id
                )
            )
            .outerjoin(
                Refund,
                and_(
                    Refund.flat_id == Flat.id,
                    Refund.event_id == event_id,
                    Refund.status == "refunded"
                )
            )
            .filter(
                Flat.society_id == society_id,
                EventFoodPass.total_amount > 0
            )
            .group_by(
                Flat.flat_number,
                EventFoodPass.total_amount,
                Payment.paid_amount
            )
            .order_by(Flat.flat_number)
            .all()
        )

        pending = []
        for r in results:
            remaining = r.expected_amount - r.paid_amount - r.refunded_amount
            if remaining <= 0:
                continue
            pending.append({
                "flat": r.flat_number,
                "expected": r.expected_amount,
                "paid": r.paid_amount,
                "refunded": r.refunded_amount,
                "pending": remaining
            })

        return pending
