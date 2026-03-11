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
    def _legacy_generate_rows(db: Session, event_id, flats):
        rows = []
        for flat in flats:
            payment = db.query(Payment).filter(
                Payment.event_id == event_id,
                Payment.flat_id == flat.id
            ).first()

            paid = payment.paid_amount if payment else 0
            expected = payment.expected_amount if payment else 0
            refunded = (
                db.query(func.coalesce(func.sum(Refund.amount), 0))
                .filter(
                    Refund.event_id == event_id,
                    Refund.flat_id == flat.id,
                    Refund.status.in_(["approved", "refunded"]),
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
                "System",
            ])
        return rows

    @staticmethod
    @log_service_call(logger, "FlatPaymentReport.generate")
    def generate(db: Session, event_id):
        context = build_log_context(event_id=event_id)
        rows = []

        base_query = db.query(
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
        if not hasattr(base_query, "outerjoin"):
            rows = FlatPaymentReport._legacy_generate_rows(db, event_id, base_query.all())
        else:
            records = (
                base_query
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
