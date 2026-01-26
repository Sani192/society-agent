#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 25 16:10:24 2026

@author: anonymous
"""

from sqlalchemy.orm import Session
from app.db.models import AuditLog


def log_report_access(
    db: Session,
    *,
    society_id,
    event_id,
    report_code: str,
    performed_by,
    format: str
):
    log = AuditLog(
        society_id=society_id,
        entity_type="REPORT",
        entity_id=event_id or society_id,
        action=f"VIEW_{report_code}",
        reason=f"format={format}",
        performed_by=performed_by
    )

    db.add(log)
    db.commit()
