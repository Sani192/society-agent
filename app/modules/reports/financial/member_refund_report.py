#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Feb  8 14:58:17 2026

@author: anonymous
"""

import logging
from sqlalchemy.orm import Session
from app.db.models import Refund, Flat, CommitteeMember
from app.utils.logging_helpers import build_log_context, log_service_call

logger = logging.getLogger(__name__)

def format_timestamp(value):
    return value.strftime("%d %b %Y %H:%M") if value else "-"


class MemberRefundReport:

    @staticmethod
    @log_service_call(logger, "MemberRefundReport.generate")
    def generate(db: Session, *, event_id):
        context = build_log_context(event_id=event_id)
        records = (
            db.query(
                Flat.flat_number,
                Refund.amount,
                Refund.reason,
                Refund.created_at,
                CommitteeMember.name.label("created_by")
            )
            .join(Flat, Flat.id == Refund.flat_id)
            .outerjoin(
                CommitteeMember,
                CommitteeMember.id == Refund.created_by
            )
            .filter(
                Refund.event_id == event_id,
                Refund.status.in_(["approved", "refunded"])
            )
            .order_by(Refund.created_at)
            .all()
        )
        if not records:
            logger.info(
                "Workflow decision: no member refunds found | context=%s",
                context
            )

        rows = []
        for r in records:
            rows.append([
                r.flat_number,
                r.amount,
                r.reason,
                format_timestamp(r.created_at),
                r.created_by or "System"
            ])

        return {
            "headers": [
                "Flat",
                "Refund Amount",
                "Reason",
                "Created At",
                "Created By"
            ],
            "rows": rows
        }
