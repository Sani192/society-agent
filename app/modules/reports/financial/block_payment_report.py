#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jan 23 16:55:03 2026

@author: anonymous
"""

import logging
from datetime import datetime
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.db.models import Flat, Payment
from app.utils.logging_helpers import build_log_context, log_service_call

logger = logging.getLogger(__name__)


def format_timestamp(value: datetime | None) -> str:
    return value.strftime("%d %b %Y %H:%M") if value else "-"


class BlockPaymentReport:

    @staticmethod
    @log_service_call(logger, "BlockPaymentReport.generate")
    def generate(db: Session, event_id: int):
        context = build_log_context(event_id=event_id)

        records = (
            db.query(
                Flat.block.label("block"),
                func.coalesce(func.sum(Payment.expected_amount), 0).label("expected"),
                func.coalesce(func.sum(Payment.paid_amount), 0).label("paid"),
                func.max(Payment.paid_at).label("latest_paid_at"),
                func.max(Payment.updated_at).label("latest_updated_at"),
            )
            .join(Payment, Payment.flat_id == Flat.id)
            .filter(Payment.event_id == event_id)
            .group_by(Flat.block)
            .order_by(Flat.block.asc())
            .all()
        )

        rows = []
        for block, expected, paid, latest_paid_at, latest_updated_at in records:
            rows.append([
                block,
                expected,
                paid,
                expected - paid,
                format_timestamp(latest_paid_at),
                "System",
                format_timestamp(latest_updated_at),
                "System",
            ])

        if not rows:
            logger.info(
                "Workflow decision: block payment report empty | context=%s",
                context,
            )
        return {
            "headers": [
                "Block",
                "Expected",
                "Paid",
                "Pending",
                "Created At",
                "Created By",
                "Updated At",
                "Updated By",
            ],
            "rows": rows,
        }
