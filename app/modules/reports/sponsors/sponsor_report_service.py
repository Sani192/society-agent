#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jan 19 22:58:27 2026

@author: anonymous
"""

# app/modules/reports/sponsors/sponsor_report_service.py

import logging
from sqlalchemy.orm import Session

from app.db.models import EventContribution
from app.utils.logging_helpers import build_log_context, log_service_call

logger = logging.getLogger(__name__)


class SponsorReport:

    @staticmethod
    @log_service_call(logger, "SponsorReport.generate")
    def generate(db: Session, *, event_id: str):
        context = build_log_context(event_id=event_id)
        rows = (
            db.query(EventContribution)
            .filter(
                EventContribution.event_id == event_id
            )
            .order_by(EventContribution.created_at)
            .all()
        )
        if not rows:
            logger.info(
                "Workflow decision: no sponsor contributions found | context=%s",
                context
            )

        result = []

        for c in rows:
            if c.amount and c.amount > 0:
                result.append({
                    "name": c.source_name,
                    "type": "cash",
                    "amount": int(c.amount)
                })
            else:
                result.append({
                    "name": c.source_name,
                    "type": "in_kind",
                    "details": c.in_kind_details or {}
                })

        if not result:
            logger.info(
                "Workflow decision: no sponsor report entries built | context=%s",
                context
            )
        return result
