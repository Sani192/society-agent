#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 25 16:22:26 2026

@author: anonymous
"""

import logging
from sqlalchemy.orm import Session
from app.db.models import EventContribution, Flat
from app.utils.logging_helpers import build_log_context, log_service_call

logger = logging.getLogger(__name__)


class SponsorContributionReport:

    @staticmethod
    @log_service_call(logger, "SponsorContributionReport.generate")
    def generate(db: Session, event_id):
        context = build_log_context(event_id=event_id)
        records = (
            db.query(
                EventContribution.contribution_type,
                EventContribution.source_name,
                EventContribution.contribution_code,
                Flat.flat_number,
                EventContribution.amount,
                EventContribution.in_kind_details
            )
            .outerjoin(Flat, Flat.id == EventContribution.flat_id)
            .filter(EventContribution.event_id == event_id)
            .all()
        )
        if not records:
            logger.info(
                "Workflow decision: no sponsor contributions found | context=%s",
                context
            )

        rows = []
        total_cash = 0

        for ctype, source, code, flat, amount, in_kind in records:
            cash = amount or 0
            total_cash += cash

            rows.append([
                ctype,
                source,
                code,
                flat or "-",
                cash,
                in_kind or "-"
            ])

        if not rows:
            logger.info(
                "Workflow decision: sponsor contribution report empty | context=%s",
                context
            )
        return {
            "headers": [
                "Contribution Type",
                "Source",
                "Contribution Code",
                "Flat",
                "Cash Amount",
                "In-kind Contribution"
            ],
            "rows": rows,
            "total_cash": total_cash
        }
