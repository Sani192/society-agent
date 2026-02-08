#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 11 05:57:35 2026

@author: anonymous
"""

# app/modules/reports/sponsor_wise.py

import logging
from sqlalchemy.orm import Session

from app.db.models import EventContribution
from app.modules.reports.common.resolvers import get_event_or_raise
from app.utils.logging_helpers import build_log_context, log_service_call

logger = logging.getLogger(__name__)


class SponsorWiseReport:

    @staticmethod
    @log_service_call(logger, "SponsorWiseReport.generate")
    def generate(db: Session, *, event_id):
        context = build_log_context(event_id=event_id)
        get_event_or_raise(db, event_id)
        contributions = (
            db.query(EventContribution)
            .filter(EventContribution.event_id == event_id)
            .all()
        )
        if not contributions:
            logger.info(
                "Workflow decision: no sponsor-wise contributions found | context=%s",
                context
            )

        result = [
            {
                "source": c.source_name,
                "type": c.contribution_type,
                "amount": c.amount,
                "notes": c.notes
            }
            for c in contributions
        ]
        if not result:
            logger.info(
                "Workflow decision: sponsor-wise report empty | context=%s",
                context
            )
        return result
