#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 11 05:58:01 2026

@author: anonymous
"""

# app/modules/reports/override_report.py

import logging
from sqlalchemy.orm import Session

from app.db.models import AuditLog
from app.modules.reports.common.resolvers import get_event_or_raise
from app.utils.logging_helpers import build_log_context, log_service_call

logger = logging.getLogger(__name__)


class OverrideReport:

    @staticmethod
    @log_service_call(logger, "OverrideReport.generate")
    def generate(db: Session, *, event_id):
        context = build_log_context(event_id=event_id)
        get_event_or_raise(db, event_id)
        logs = (
            db.query(AuditLog)
            .filter(
                AuditLog.entity_id == event_id,
                AuditLog.reason.like("OVERRIDE%")
            )
            .order_by(AuditLog.performed_at)
            .all()
        )
        if not logs:
            logger.info(
                "Workflow decision: no override logs found | context=%s",
                context
            )

        result = [
            {
                "action": log.action,
                "reason": log.reason,
                "performed_at": log.performed_at
            }
            for log in logs
        ]
        if not result:
            logger.info(
                "Workflow decision: override report empty | context=%s",
                context
            )
        return result
