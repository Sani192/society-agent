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
    format: str,
    source: str = "reports_api",
    trace_id: str | None = None,
    correlation_id: str | None = None,
):
    log = AuditLog(
        society_id=society_id,
        entity_type="REPORT",
        entity_id=event_id or society_id,
        action=f"VIEW_{report_code}",
        reason=f"format={format}",
        source=source,
        trace_id=trace_id,
        correlation_id=correlation_id,
        metadata_json={"format": format, "report_code": report_code},
        performed_by=performed_by
    )

    db.add(log)



def log_announcement_creation(
    db: Session,
    *,
    society_id,
    announcement_id,
    announcement_type: str,
    message_text: str,
    performed_by,
):
    preview = (message_text or "").strip().replace("\n", " ")[:80]
    reason = f"type={announcement_type}; preview={preview}" if preview else f"type={announcement_type}"

    log = AuditLog(
        society_id=society_id,
        entity_type="announcement",
        entity_id=announcement_id,
        action="CREATE_ANNOUNCEMENT",
        reason=reason,
        performed_by=performed_by,
    )

    db.add(log)
