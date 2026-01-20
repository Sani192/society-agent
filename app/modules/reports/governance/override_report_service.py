#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jan 19 23:20:29 2026

@author: anonymous
"""

# app/modules/reports/governance/override_report_service.py

from sqlalchemy.orm import Session

from app.db.models import AuditLog, CommitteeMember


class OverrideReport:

    @staticmethod
    def generate(db: Session, *, society_id: str):
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

        result = []
        for entity, action, reason, ts, role in rows:
            result.append({
                "entity": entity,
                "action": action,
                "reason": reason or "",
                "performed_by": role,
                "date": ts.date().isoformat()
            })

        return result
