#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jan 23 16:55:03 2026

@author: anonymous
"""

from collections import defaultdict
from sqlalchemy.orm import Session
from app.db.models import Flat, Payment

class BlockPaymentReport:

    @staticmethod
    def generate(db: Session, event_id):
        data = defaultdict(lambda: {"expected": 0, "paid": 0})

        flats = db.query(Flat).all()
        for flat in flats:
            payment = db.query(Payment).filter(
                Payment.event_id == event_id,
                Payment.flat_id == flat.id
            ).first()

            if payment:
                data[flat.block]["expected"] += payment.expected_amount
                data[flat.block]["paid"] += payment.paid_amount

        rows = []
        for block, values in data.items():
            rows.append([
                block,
                values["expected"],
                values["paid"],
                values["expected"] - values["paid"]
            ])

        return {
            "headers": ["Block", "Expected", "Paid", "Pending"],
            "rows": rows
        }
