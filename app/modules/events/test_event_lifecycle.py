#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Jan 10 14:37:47 2026

@author: anonymous
"""

from app.db.session import SessionLocal
from app.db.models import Event, CommitteeMember
from app.modules.events.service import EventService

def run():
    db = SessionLocal()

    event = db.query(Event).first()
    member = db.query(CommitteeMember).first()

    EventService.activate_event(
        db=db,
        event_id=event.id,
        performed_by=member.id
    )

    EventService.lock_passes(
        db=db,
        event_id=event.id,
        performed_by=member.id
    )

    EventService.start_event_day(
        db=db,
        event_id=event.id,
        performed_by=member.id
    )

    EventService.close_event(
        db=db,
        event_id=event.id,
        performed_by=member.id
    )

    print("✅ Event lifecycle completed")

    db.close()

if __name__ == "__main__":
    run()
