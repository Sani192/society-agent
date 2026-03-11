#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Dedicated scheduler worker entrypoint."""

from __future__ import annotations

import signal
import time

from app.db.base import Base
from app.db.models import Society
from app.db.session import SessionLocal, engine
from app.modules.announcements.delivery_worker import (
    acquire_announcement_scheduler_leader_lock,
    announcement_delivery_scheduler,
    start_announcement_delivery_scheduler,
)
from app.modules.reminders.reminder_scheduler import (
    acquire_scheduler_leader_lock,
    scheduler,
    start_scheduler,
)
from app.utils.logger import logger


_running = True
_lock_sessions = []


def _handle_signal(signum, _frame):
    global _running
    logger.info("Scheduler worker received shutdown signal", extra={"signal": signum})
    _running = False


def _startup_checks() -> bool:
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        society = db.query(Society).first()
        if not society:
            logger.warning("No society found in database")
            return False
        logger.info(f"Loaded society: {society.name}")
        return True
    finally:
        db.close()


def main() -> int:
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    if not _startup_checks():
        return 1

    reminder_lock = acquire_scheduler_leader_lock()
    announcement_lock = acquire_announcement_scheduler_leader_lock()

    if reminder_lock and announcement_lock:
        _lock_sessions.extend([reminder_lock, announcement_lock])
        logger.info(
            "Scheduler worker startup",
            extra={"scheduler_role": "leader"},
        )
        start_scheduler()
        start_announcement_delivery_scheduler()
    else:
        if reminder_lock:
            reminder_lock.close()
        if announcement_lock:
            announcement_lock.close()
        logger.info(
            "Scheduler worker startup",
            extra={"scheduler_role": "follower"},
        )

    while _running:
        time.sleep(1)

    if scheduler.running:
        scheduler.shutdown(wait=False)
    if announcement_delivery_scheduler.running:
        announcement_delivery_scheduler.shutdown(wait=False)

    for session in _lock_sessions:
        session.close()

    logger.info("Scheduler worker shutting down")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
