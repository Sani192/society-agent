#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jan 19 23:22:36 2026

@author: anonymous
"""

# app/modules/reports/governance/audit_summary_service.py

import logging
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.models import AuditLog, Refund
from app.utils.logging_helpers import build_log_context, log_service_call

logger = logging.getLogger(__name__)


class AuditSummaryReport:

    @staticmethod
    @log_service_call(logger, "AuditSummaryReport.generate")
    def generate(db: Session, *, society_id: str):
        context = build_log_context(society_id=society_id)
        overrides = (
            db.query(func.count(AuditLog.id))
            .filter(
                AuditLog.society_id == society_id,
                AuditLog.action.ilike("OVERRIDE%")
            )
            .scalar()
        )

        refunds = (
            db.query(func.count(Refund.id))
            .filter(
                Refund.status == "refunded"
            )
            .scalar()
        )
        logger.info(
            "Workflow decision: computed audit summary counts | context=%s",
            context
        )

        return {
            "total_overrides": int(overrides or 0),
            "total_refunds": int(refunds or 0),
            "late_changes": int(overrides or 0)  # proxy for now
        }
