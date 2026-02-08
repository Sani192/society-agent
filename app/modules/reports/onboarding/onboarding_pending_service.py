#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jan 19 23:11:09 2026

@author: anonymous
"""

# app/modules/reports/onboarding/onboarding_pending_service.py

import logging
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.db.models import PendingUser
from app.utils.logging_helpers import build_log_context, log_service_call

logger = logging.getLogger(__name__)


class OnboardingPendingReport:

    @staticmethod
    @log_service_call(logger, "OnboardingPendingReport.generate")
    def generate(db: Session, *, society_id: str):
        context = build_log_context(society_id=society_id)
        rows = (
            db.query(PendingUser)
            .filter(
                PendingUser.society_id == society_id,
                PendingUser.status == "pending"
            )
            .order_by(PendingUser.created_at)
            .all()
        )
        if not rows:
            logger.info(
                "Workflow decision: no pending onboarding requests | context=%s",
                context
            )

        result = []
        now = datetime.now(timezone.utc)

        for r in rows:
            days = (now - r.created_at).days
            result.append({
                "request_code": r.request_code,
                "flat_number": r.flat_number,
                "waiting_days": days
            })

        if not result:
            logger.info(
                "Workflow decision: onboarding report empty | context=%s",
                context
            )
        return result
