#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Jan 10 14:28:50 2026

@author: anonymous
"""

# app/modules/events/test_create_event.py

from datetime import datetime

from app.db.session import SessionLocal
from app.modules.events.service import EventService
from app.db.models import Society, CommitteeMember


def run_test():
    db = SessionLocal()

    society = db.query(Society).first()
    member = db.query(CommitteeMember).first()

    event = EventService.create_event(
        db=db,
        society_id=society.id,
        name="Ganesh Chaturthi Dinner",
        event_date=datetime(2026, 9, 14, 19, 0),
        food_types=["veg", "jain"],
        charge_per_person=300,
        payment_deadline=datetime(2026, 9, 10, 23, 59),
        created_by=member.id
    )

    print("✅ Event Created:", event.id)

    db.close()


if __name__ == "__main__":
    run_test()
