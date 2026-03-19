#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jan 23 16:54:23 2026

@author: anonymous
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
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
        records = (
            db.query(
                Flat.flat_number,
                Flat.block,
                func.coalesce(func.max(Payment.expected_amount), 0).label("expected"),
                func.coalesce(func.sum(Payment.paid_amount), 0).label("paid"),
                func.coalesce(
                    func.sum(Refund.amount).filter(
                        Refund.status.in_(["approved", "refunded"])
                    ),
                    0,
                ).label("refunded"),
                func.max(Payment.paid_at).label("paid_at"),
                func.max(Payment.updated_at).label("updated_at"),
            )
            .outerjoin(
                Payment,
                and_(Payment.flat_id == Flat.id, Payment.event_id == event_id),
            )
            .outerjoin(
                Refund,
                and_(Refund.flat_id == Flat.id, Refund.event_id == event_id),
            )
            .group_by(Flat.id, Flat.flat_number, Flat.block)
            .order_by(Flat.block.asc(), Flat.flat_number.asc())
            .all()
        )

        rows = []
        if not records:
            logger.info(
                "Workflow decision: no flats found for flat payment report | context=%s",
                context
            )
        for flat_number, block, expected, paid, refunded, paid_at, updated_at in records:
            net_paid = paid - refunded
            pending = expected - net_paid

            rows.append([
                flat_number,
                block,
                expected,
                paid,
                refunded,
                pending,
                format_timestamp(paid_at),
                "System",
                format_timestamp(updated_at),
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
