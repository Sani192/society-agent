#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jan 26 10:27:51 2026

@author: anonymous
"""

from sqlalchemy.orm import Session
from app.db.models import AuditLog, CommitteeMember


class GovernanceAuditReport:

    @staticmethod
    def generate(db: Session, society_id):
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

        rows = [
            [
                performed_at.strftime("%d %b %Y %H:%M"),
                action,
                reason or "-",
                name,
                role
            ]
            for performed_at, action, reason, name, role in records
        ]

        return {
            "headers": [
                "Date & Time",
                "Action",
                "Reason",
                "Performed By",
                "Role"
            ],
            "rows": rows
        }
