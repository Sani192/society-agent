#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jan 19 23:22:36 2026

@author: anonymous
"""

# app/modules/reports/governance/audit_summary_service.py

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.models import AuditLog, Refund


class AuditSummaryReport:

    @staticmethod
    def generate(db: Session, *, society_id: str):
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

        return {
            "total_overrides": int(overrides or 0),
            "total_refunds": int(refunds or 0),
            "late_changes": int(overrides or 0)  # proxy for now
        }
