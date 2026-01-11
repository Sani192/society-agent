#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 11 05:58:01 2026

@author: anonymous
"""

# app/modules/reports/override_report.py

from sqlalchemy.orm import Session

from app.db.models import AuditLog


class OverrideReport:

    @staticmethod
    def generate(db: Session, *, event_id):
        logs = (
            db.query(AuditLog)
            .filter(
                AuditLog.entity_id == event_id,
                AuditLog.reason.like("OVERRIDE%")
            )
            .order_by(AuditLog.performed_at)
            .all()
        )

        return [
            {
                "action": log.action,
                "reason": log.reason,
                "performed_at": log.performed_at
            }
            for log in logs
        ]
