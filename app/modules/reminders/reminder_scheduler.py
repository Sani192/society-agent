#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Jan 17 12:03:14 2026

@author: anonymous
"""

# app/modules/reminders/reminder_scheduler.py

from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from app.db.session import SessionLocal
from app.db.models import Event, ReminderConfig, WorkflowState
from app.modules.events.service import EventService
from app.modules.reminders.reminder_service import ReminderService
from app.utils.logger import logger

scheduler = BackgroundScheduler()
AUTO_CLOSE_SOURCE = "system:auto_close_job"
AUTO_CLOSE_MIN_AGE_HOURS = 2


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


def start_scheduler():
    db = SessionLocal()
    try:
        configs = (
            db.query(ReminderConfig)
            .filter(ReminderConfig.enabled.is_(True))
            .all()
        )

        for config in configs:
            scheduler.add_job(
                run_payment_reminders,
                trigger="cron",
                hour=config.run_hour,
                minute=config.run_minute,
                args=[config.society_id],
                id=f"reminder_{config.society_id}",
                replace_existing=True
            )

            scheduler.add_job(
                run_event_auto_close_job,
                trigger="cron",
                hour=config.run_hour,
                minute=config.run_minute,
                args=[config.society_id],
                id=f"auto_close_{config.society_id}",
                replace_existing=True
            )

            logger.info(
                f"Scheduler loaded for society {config.society_id} "
                f"at {config.run_hour:02d}:{config.run_minute:02d}"
            )
            logger.info(
                f"Auto-close scheduler loaded for society {config.society_id} "
                f"at {config.run_hour:02d}:{config.run_minute:02d}"
            )

        scheduler.start()
    finally:
        db.close()
