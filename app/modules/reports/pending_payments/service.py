#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jan 19 21:45:37 2026

@author: anonymous
"""

# app/modules/reports/pending_payments/service.py

import logging
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.db.models import Payment, Flat
from app.utils.logging_helpers import build_log_context, log_service_call

logger = logging.getLogger(__name__)


class PendingPaymentsReport:

    @staticmethod
    @log_service_call(logger, "PendingPaymentsReport.generate")
    def generate(db: Session, *, event_id: str):
        context = build_log_context(event_id=event_id)
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
        if not rows:
            logger.info(
                "Workflow decision: no pending payments found | context=%s",
                context
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

        if not result:
            logger.info(
                "Workflow decision: no pending payment rows qualified | context=%s",
                context
            )
        return result
