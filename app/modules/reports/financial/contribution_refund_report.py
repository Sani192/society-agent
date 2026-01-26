#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 25 16:53:39 2026

@author: anonymous
"""

from sqlalchemy.orm import Session
from app.db.models import (
    ContributionRefund,
    EventContribution
)


class ContributionRefundReport:

    @staticmethod
    def generate(db: Session, event_id):
        records = (
            db.query(
                EventContribution.contribution_type,
                EventContribution.source_name,
                ContributionRefund.amount,
                ContributionRefund.reason,
                ContributionRefund.status
            )
            .join(
                EventContribution,
                EventContribution.id == ContributionRefund.contribution_id
            )
            .filter(EventContribution.event_id == event_id)
            .all()
        )

        rows = []
        total_refunded = 0

        for ctype, source, amount, reason, status in records:
            refunded_amount = amount or 0
            if status == "refunded":
                total_refunded += refunded_amount

            rows.append([
                ctype,
                source,
                refunded_amount,
                reason,
                status
            ])

        return {
            "headers": [
                "Contribution Type",
                "Source",
                "Refund Amount",
                "Reason",
                "Status"
            ],
            "rows": rows,
            "total_refunded": total_refunded
        }
