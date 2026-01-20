#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Jan 17 12:03:14 2026

@author: anonymous
"""

# app/modules/reminders/reminder_scheduler.py

from apscheduler.schedulers.background import BackgroundScheduler
from app.db.session import SessionLocal
from app.db.models import Event, ReminderConfig
from app.modules.reminders.reminder_service import ReminderService
from app.utils.logger import logger

scheduler = BackgroundScheduler()


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
            society_id=society_id,
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

            logger.info(
                f"Scheduler loaded for society {config.society_id} "
                f"at {config.run_hour:02d}:{config.run_minute:02d}"
            )

        scheduler.start()
    finally:
        db.close()

