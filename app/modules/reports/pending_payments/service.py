#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jan 19 21:45:37 2026

@author: anonymous
"""

# app/modules/reports/pending_payments/service.py

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.db.models import Payment, Flat


class PendingPaymentsReport:

    @staticmethod
    def generate(db: Session, *, event_id: str):
        rows = (
            db.query(
                Flat.flat_number,
                Flat.block,
                Payment.expected_amount,
                Payment.paid_amount
            )
            .join(Flat, Flat.id == Payment.flat_id)
            .filter(
                Payment.event_id == event_id,
                Payment.expected_amount > Payment.paid_amount,
                Flat.is_active.is_(True)
            )
            .order_by(Flat.block, Flat.flat_number)
            .all()
        )

        result = []
        for r in rows:
            pending = (r.expected_amount or 0) - (r.paid_amount or 0)
            if pending > 0:
                result.append({
                    "flat_number": r.flat_number,
                    "block": r.block,
                    "expected_amount": int(r.expected_amount or 0),
                    "paid_amount": int(r.paid_amount or 0),
                    "pending_amount": int(pending)
                })

        return result
