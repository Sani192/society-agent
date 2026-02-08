#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jan 23 16:54:23 2026

@author: anonymous
"""

from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.models import Flat, Payment, Refund

class FlatPaymentReport:

    @staticmethod
    def generate(db: Session, event_id):
        rows = []

        flats = db.query(Flat).all()
        for flat in flats:
            payment = db.query(Payment).filter(
                Payment.event_id == event_id,
                Payment.flat_id == flat.id
            ).first()

            paid = payment.paid_amount if payment else 0
            expected = payment.expected_amount if payment else 0
            
            # sum of refunds
            refunded = (
                db.query(func.coalesce(func.sum(Refund.amount), 0))
                .filter(
                    Refund.event_id == event_id,
                    Refund.flat_id == flat.id,
                    Refund.status.in_(["approved", "refunded"])
                )
                .scalar()
            )

            net_paid = paid - refunded
            pending = expected - net_paid

            rows.append([
                flat.flat_number,
                flat.block,
                expected,
                paid,
                refunded,
                pending
            ])

        return {
            "headers": ["Flat", "Block", "Expected", "Paid", "Refunded", "Pending"],
            "rows": rows
        }
