#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jan 23 16:50:57 2026

@author: anonymous
"""

import logging

from app.db.models import Event
from app.utils.logging_helpers import build_log_context

logger = logging.getLogger(__name__)

def get_event(db, event_id=None):
    if event_id:
        logger.info(
            "Workflow decision: loading specified event | context=%s",
            build_log_context(event_id=event_id)
        )
        return db.query(Event).get(event_id)
    logger.info("Workflow decision: loading most recent event | context=%s", {})
    return db.query(Event).order_by(Event.created_at.desc()).first()


def get_event_or_raise(db, event_id=None):
    event = get_event(db, event_id)
    if not event:
        logger.warning(
            "Validation failed: event not found | context=%s",
            build_log_context(event_id=event_id)
        )
        raise Exception("Event not found.")
    return event
