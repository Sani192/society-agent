#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jan 19 23:20:29 2026

@author: anonymous
"""

# app/modules/reports/governance/override_report_service.py

import logging
from sqlalchemy.orm import Session

from app.db.models import AuditLog, CommitteeMember
from app.utils.logging_helpers import build_log_context, log_service_call

logger = logging.getLogger(__name__)


class OverrideReport:

    @staticmethod
    @log_service_call(logger, "OverrideReport.generate")
    def generate(db: Session, *, society_id: str):
        context = build_log_context(society_id=society_id)
        rows = (
            db.query(
                AuditLog.entity_type,
                AuditLog.action,
                AuditLog.reason,
                AuditLog.performed_at,
                CommitteeMember.role
            )
            .join(
                CommitteeMember,
                CommitteeMember.id == AuditLog.performed_by
            )
            .filter(
                AuditLog.society_id == society_id,
                AuditLog.action.ilike("OVERRIDE%")
            )
            .order_by(AuditLog.performed_at.desc())
            .all()
        )
        if not rows:
            logger.info(
                "Workflow decision: no override audit logs found | context=%s",
                context
            )

        result = []
        for entity, action, reason, ts, role in rows:
            result.append({
                "entity": entity,
                "action": action,
                "reason": reason or "",
                "performed_by": role,
                "date": ts.date().isoformat()
            })

        if not result:
            logger.info(
                "Workflow decision: override report empty | context=%s",
                context
            )
        return result
