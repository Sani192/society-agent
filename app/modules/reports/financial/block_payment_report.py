#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jan 23 16:55:03 2026

@author: anonymous
"""

import logging
from collections import defaultdict
from sqlalchemy.orm import Session
from app.db.models import Flat, Payment
from app.utils.logging_helpers import build_log_context, log_service_call

logger = logging.getLogger(__name__)

class BlockPaymentReport:

    @staticmethod
    @log_service_call(logger, "BlockPaymentReport.generate")
    def generate(db: Session, event_id):
        context = build_log_context(event_id=event_id)
        data = defaultdict(lambda: {"expected": 0, "paid": 0})

        flats = db.query(Flat).all()
        if not flats:
            logger.info(
                "Workflow decision: no flats found for block payment report | context=%s",
                context
            )
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

        if not rows:
            logger.info(
                "Workflow decision: block payment report empty | context=%s",
                context
            )
        return {
            "headers": ["Block", "Expected", "Paid", "Pending"],
            "rows": rows
        }
