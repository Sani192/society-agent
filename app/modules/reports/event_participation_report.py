#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Feb 04 10:25:10 2026

@author: anonymous
"""

# app/modules/reports/event_participation_report.py

import logging
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.db.models import EventFoodPass, Flat
from app.utils.logging_helpers import build_log_context, log_service_call

logger = logging.getLogger(__name__)


class EventParticipationReport:

    @staticmethod
    @log_service_call(logger, "EventParticipationReport.generate")
    def generate(db: Session, *, event_id, society_id):
        context = build_log_context(event_id=event_id, society_id=society_id)
        flats = (
            db.query(Flat.flat_number)
            .filter(
                Flat.society_id == society_id,
                Flat.is_active.is_(True)
            )
            .order_by(Flat.flat_number)
            .all()
        )
        if not flats:
            logger.info(
                "Workflow decision: no flats found for participation report | context=%s",
                context
            )

        participating = (
            db.query(Flat.flat_number)
            .join(
                EventFoodPass,
                and_(
                    EventFoodPass.flat_id == Flat.id,
                    EventFoodPass.event_id == event_id,
                    EventFoodPass.is_participating.is_(True)
                )
            )
            .filter(Flat.society_id == society_id)
            .order_by(Flat.flat_number)
            .all()
        )
        if not participating:
            logger.info(
                "Workflow decision: no participating flats found | context=%s",
                context
            )

        all_flats = {f[0] for f in flats}
        participating_flats = {f[0] for f in participating}
        non_participating = sorted(all_flats - participating_flats)

        return {
            "participating": sorted(participating_flats),
            "not_participating": non_participating
        }
