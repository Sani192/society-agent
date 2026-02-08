#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 25 16:53:39 2026

@author: anonymous
"""

import logging
from sqlalchemy.orm import Session
from app.db.models import (
    ContributionRefund,
    EventContribution
)
from app.utils.logging_helpers import build_log_context, log_service_call

logger = logging.getLogger(__name__)

def format_timestamp(value):
    return value.strftime("%d %b %Y %H:%M") if value else "-"


class ContributionRefundReport:

    @staticmethod
    @log_service_call(logger, "ContributionRefundReport.generate")
    def generate(db: Session, event_id):
        context = build_log_context(event_id=event_id)
        records = (
            db.query(
                EventContribution.contribution_type,
                EventContribution.source_name,
                ContributionRefund.amount,
                ContributionRefund.reason,
                ContributionRefund.status,
                ContributionRefund.processed_at
            )
            .join(
                EventContribution,
                EventContribution.id == ContributionRefund.contribution_id
            )
            .filter(EventContribution.event_id == event_id)
            .all()
        )
        if not records:
            logger.info(
                "Workflow decision: no contribution refunds found | context=%s",
                context
            )

        rows = []
        total_refunded = 0

        for ctype, source, amount, reason, status, processed_at in records:
            refunded_amount = amount or 0
            if status == "refunded":
                total_refunded += refunded_amount

            rows.append([
                ctype,
                source,
                refunded_amount,
                reason,
                status,
                format_timestamp(processed_at),
                "System"
            ])

        if not rows:
            logger.info(
                "Workflow decision: contribution refund report empty | context=%s",
                context
            )
        return {
            "headers": [
                "Contribution Type",
                "Source",
                "Refund Amount",
                "Reason",
                "Status",
                "Created At",
                "Created By"
            ],
            "rows": rows,
            "total_refunded": total_refunded
        }
