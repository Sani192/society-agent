#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Jan 17 12:03:14 2026

@author: anonymous
"""

# app/modules/reminders/reminder_scheduler.py

from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from app.db.session import SessionLocal
from app.db.models import Event, WorkflowState
from app.modules.audit.retention_service import AuditRetentionService
from app.modules.events.service import EventService
from app.modules.reminders.reminder_service import ReminderService
from app.utils.logger import logger


AUTO_CLOSE_SOURCE = "system:auto_close_job"
AUTO_CLOSE_MIN_AGE_HOURS = 2
AUDIT_PRUNE_JOB_ID = "audit_retention_prune"


def run_payment_reminders(society_id):
    db = SessionLocal()
    try:
        event = (
            db.query(Event)
            .filter(Event.society_id == society_id)
            .order_by(Event.created_at.desc())
            .first()
        )

        if not event:
            return

        generated = ReminderService.generate_pending_payment_reminders(
            db=db,
            event_id=event.id
        )

        if generated:
            logger.info(
                f"[Reminder] Generated {len(generated)} reminders "
                f"for society {society_id}"
            )
    except Exception:
        logger.exception("Error running payment reminder job")
    finally:
        db.close()


def _format_auto_close_reason(hours_past_event):
    return f"AUTO_CLOSE: event_date passed by {hours_past_event} hours"


def run_event_auto_close_job(society_id, min_age_hours=AUTO_CLOSE_MIN_AGE_HOURS):
    db = SessionLocal()
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=min_age_hours)

    try:
        eligible_events = (
            db.query(Event)
            .join(WorkflowState, WorkflowState.event_id == Event.id)
            .filter(Event.society_id == society_id)
            .filter(Event.status != "CLOSED")
            .filter(WorkflowState.current_state != "CLOSED")
            .filter(Event.event_date <= cutoff)
            .all()
        )

        for event in eligible_events:
            hours_past_event = int((now - event.event_date).total_seconds() // 3600)
            try:
                EventService.close_event(
                    db=db,
                    event_id=event.id,
                    performed_by=None,
                    source=AUTO_CLOSE_SOURCE,
                    reason=_format_auto_close_reason(hours_past_event),
                    action="AUTO_CLOSE_EVENT"
                )
            except Exception:
                logger.exception(
                    "Failed auto-close for event_id=%s society_id=%s",
                    event.id,
                    event.society_id
                )
    except Exception:
        logger.exception("Error running auto-close job")
    finally:
        db.close()


def run_audit_retention_prune():
    db = SessionLocal()
    try:
        deleted_counts = AuditRetentionService.prune(db)
        logger.info("Audit retention prune completed | deleted=%s", deleted_counts)
    except Exception:
        db.rollback()
        logger.exception("Error running audit retention prune job")
    finally:
        db.close()

