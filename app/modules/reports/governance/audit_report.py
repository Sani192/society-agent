#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jan 26 10:27:51 2026

@author: anonymous
"""

import logging
from sqlalchemy.orm import Session
from app.db.models import AuditLog, CommitteeMember
from app.i18n.catalog import translate
from app.utils.logging_helpers import build_log_context, log_service_call

logger = logging.getLogger(__name__)

def format_timestamp(value):
    return value.strftime("%d %b %Y %H:%M") if value else "-"


class GovernanceAuditReport:

    @staticmethod
    @log_service_call(logger, "GovernanceAuditReport.generate")
    def generate(db: Session, society_id, *, lang: str | None = None):
        context = build_log_context(society_id=society_id)
        records = (
            db.query(
                AuditLog.performed_at,
                AuditLog.action,
                AuditLog.reason,
                AuditLog.performed_by,
                CommitteeMember.name,
                CommitteeMember.role
            )
            .outerjoin(
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

        system_label = translate("report_exports.labels.system", lang)
        not_available = translate("report_exports.labels.not_available", lang)
        rows = [
            [
                format_timestamp(performed_at),
                action,
                reason or not_available,
                name or system_label,
                role if performed_by else not_available
            ]
            for performed_at, action, reason, performed_by, name, role in records
        ]

        return {
            "header_keys": ["created_at", "action", "reason", "created_by", "role"],
            "headers": [
                translate("report_exports.labels.headers.created_at", lang),
                translate("report_exports.labels.headers.action", lang),
                translate("report_exports.labels.headers.reason", lang),
                translate("report_exports.labels.headers.created_by", lang),
                translate("report_exports.labels.headers.role", lang),
            ],
            "rows": rows
        }
