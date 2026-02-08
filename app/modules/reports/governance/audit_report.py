#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jan 26 10:27:51 2026

@author: anonymous
"""

import logging
from sqlalchemy.orm import Session
from app.db.models import AuditLog, CommitteeMember
from app.utils.logging_helpers import build_log_context, log_service_call

logger = logging.getLogger(__name__)

def format_timestamp(value):
    return value.strftime("%d %b %Y %H:%M") if value else "-"


class GovernanceAuditReport:

    @staticmethod
    @log_service_call(logger, "GovernanceAuditReport.generate")
    def generate(db: Session, society_id):
        context = build_log_context(society_id=society_id)
        records = (
            db.query(
                AuditLog.performed_at,
                AuditLog.action,
                AuditLog.reason,
                CommitteeMember.name,
                CommitteeMember.role
            )
            .join(
                CommitteeMember,
                CommitteeMember.id == AuditLog.performed_by
            )
            .filter(AuditLog.society_id == society_id)
            .order_by(AuditLog.performed_at.desc())
            .all()
        )
        if not records:
            logger.info(
                "Workflow decision: no governance audit records found | context=%s",
                context
            )

        rows = [
            [
                format_timestamp(performed_at),
                action,
                reason or "-",
                name or "System",
                role
            ]
            for performed_at, action, reason, name, role in records
        ]

        return {
            "headers": [
                "Created At",
                "Action",
                "Reason",
                "Created By",
                "Role"
            ],
            "rows": rows
        }
