#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Dedicated unified scheduler worker entrypoint."""

from __future__ import annotations

import os
import sys
import time
import signal

# Ensure the root project directory is on the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.base import Base
from app.db.models import Society
from app.db.session import SessionLocal, engine
from app.modules.scheduler.manager import (
    acquire_scheduler_leader_lock,
    start_scheduler_manager,
    unified_scheduler
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

    lock = acquire_scheduler_leader_lock()

    if lock:
        _lock_sessions.append(lock)
        logger.info(
            "Scheduler worker startup",
            extra={"scheduler_role": "leader"},
        )
        start_scheduler_manager()
    else:
        logger.info(
            "Scheduler worker startup",
            extra={"scheduler_role": "follower"},
        )

    while _running:
        time.sleep(1)

    if unified_scheduler.running:
        unified_scheduler.shutdown(wait=False)

    for session in _lock_sessions:
        session.close()

    logger.info("Scheduler worker shutting down")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
