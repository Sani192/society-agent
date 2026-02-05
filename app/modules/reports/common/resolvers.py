#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jan 23 16:50:57 2026

@author: anonymous
"""

from app.db.models import Event

def get_event(db, event_id=None):
    if event_id:
        return db.query(Event).get(event_id)
    return db.query(Event).order_by(Event.created_at.desc()).first()


def get_event_or_raise(db, event_id=None):
    event = get_event(db, event_id)
    if not event:
        raise Exception("Event not found.")
    return event
