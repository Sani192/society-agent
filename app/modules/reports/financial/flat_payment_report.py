#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jan 23 16:54:23 2026

@author: anonymous
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.models import Flat, Payment, Refund
from app.utils.logging_helpers import build_log_context, log_service_call

logger = logging.getLogger(__name__)

def format_timestamp(value):
    return value.strftime("%d %b %Y %H:%M") if value else "-"

class FlatPaymentReport:

    @staticmethod
    @log_service_call(logger, "FlatPaymentReport.generate")
    def generate(db: Session, event_id):
        context = build_log_context(event_id=event_id)
        rows = []

        flats = db.query(Flat).all()
        if not flats:
            logger.info(
                "Workflow decision: no flats found for flat payment report | context=%s",
                context
            )
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
                pending,
                format_timestamp(payment.paid_at if payment else None),
                "System",
                format_timestamp(payment.updated_at if payment else None),
                "System"
            ])

        if not rows:
            logger.info(
                "Workflow decision: flat payment report empty | context=%s",
                context
            )
        return {
            "headers": [
                "Flat",
                "Block",
                "Expected",
                "Paid",
                "Refunded",
                "Pending",
                "Created At",
                "Created By",
                "Updated At",
                "Updated By"
            ],
            "rows": rows
        }
