#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jan 23 16:55:03 2026

@author: anonymous
"""

import logging
from collections import defaultdict
from datetime import datetime
from typing import TypedDict, cast
from sqlalchemy.orm import Session
from app.db.models import Flat, Payment
from app.utils.logging_helpers import build_log_context, log_service_call

logger = logging.getLogger(__name__)


def format_timestamp(value: datetime | None) -> str:
    return value.strftime("%d %b %Y %H:%M") if value else "-"


class BlockStats(TypedDict):
    expected: int
    paid: int
    latest_paid_at: datetime | None
    latest_updated_at: datetime | None


class BlockPaymentReport:

    @staticmethod
    @log_service_call(logger, "BlockPaymentReport.generate")
    def generate(db: Session, event_id: int):
        context = build_log_context(event_id=event_id)
        data: defaultdict[str, BlockStats] = defaultdict(
            lambda: {
                "expected": 0,
                "paid": 0,
                "latest_paid_at": None,
                "latest_updated_at": None,
            }
        )

        flats = db.query(Flat).all()
        if not flats:
            logger.info(
                "Workflow decision: no flats found for block payment report | context=%s",
                context,
            )
        for flat in flats:
            payment = db.query(Payment).filter(
                Payment.event_id == event_id,
                Payment.flat_id == flat.id,
            ).first()

            if payment:
                block_key = str(flat.block)
                expected_amount = int(payment.expected_amount)
                paid_amount = int(payment.paid_amount)
                paid_at = cast(datetime | None, payment.paid_at)
                updated_at = cast(datetime | None, payment.updated_at)

                data[block_key]["expected"] += expected_amount
                data[block_key]["paid"] += paid_amount
                current_latest_paid = data[block_key]["latest_paid_at"]
                if paid_at and (
                    current_latest_paid is None
                    or paid_at > current_latest_paid
                ):
                    data[block_key]["latest_paid_at"] = paid_at

                current_latest_updated = data[block_key]["latest_updated_at"]
                if updated_at and (
                    current_latest_updated is None
                    or updated_at > current_latest_updated
                ):
                    data[block_key]["latest_updated_at"] = updated_at

        rows = []
        for block, values in data.items():
            rows.append([
                block,
                values["expected"],
                values["paid"],
                values["expected"] - values["paid"],
                format_timestamp(values["latest_paid_at"]),
                "System",
                format_timestamp(values["latest_updated_at"]),
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
