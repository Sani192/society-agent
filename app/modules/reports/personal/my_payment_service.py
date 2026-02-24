#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jan 19 22:02:42 2026

@author: anonymous
"""

# app/modules/reports/personal/my_payment_service.py

import logging
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.models import (
    UserFlatMapping,
    Payment,
    Refund,
    MemberIdentity
)
from app.utils.logging_helpers import build_log_context, log_service_call

logger = logging.getLogger(__name__)


class MyPaymentReport:

    @staticmethod
    @log_service_call(logger, "MyPaymentReport.generate")
    def generate(
        db: Session,
        *,
        society_id: str,
        event_id: str,
        user_identifier: str
    ):
        context = build_log_context(
            event_id=event_id,
            society_id=society_id
        )
        # 1️ Resolve user's flat
        mapping = (
            db.query(UserFlatMapping)
            .join(MemberIdentity, MemberIdentity.id == UserFlatMapping.member_identity_id)
            .filter(
                UserFlatMapping.society_id == society_id,
                MemberIdentity.normalized_identifier == user_identifier,
                UserFlatMapping.is_active.is_(True)
            )
            .first()
        )

        if not mapping:
            logger.warning(
                "Validation failed: user not mapped to flat | context=%s",
                context
            )
            raise Exception("You are not registered with this society.")

        # 2️ Load payment record
        payment = (
            db.query(Payment)
            .filter(
                Payment.event_id == event_id,
                Payment.flat_id == mapping.flat_id
            )
            .first()
        )

        if not payment:
            logger.info(
                "Workflow decision: no payment record found | context=%s",
                context
            )
            return {
                "expected": 0,
                "paid": 0,
                "refunded": 0,
                "pending": 0,
                "status": "not_applicable"
            }

        # 3️ Sum refunds
        refunded = (
            db.query(func.coalesce(func.sum(Refund.amount), 0))
            .filter(
                Refund.event_id == event_id,
                Refund.flat_id == mapping.flat_id,
                Refund.status == "refunded"
            )
            .scalar()
        )

        expected = int(payment.expected_amount or 0)
        paid = int(payment.paid_amount or 0)
        refunded = int(refunded or 0)
        pending = max(expected - paid, 0)

        if pending == 0 and paid > 0:
            status = "paid"
        elif paid > 0:
            status = "partial"
        else:
            status = "pending"
        logger.info(
            "Workflow decision: resolved payment status %s | context=%s",
            status,
            context
        )

        return {
            "expected": expected,
            "paid": paid,
            "refunded": refunded,
            "pending": pending,
            "status": status
        }
