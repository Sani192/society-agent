#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 11 20:55:02 2026

@author: anonymous
"""

# scripts/reset_event.py

from app.db.session import SessionLocal
from app.db.models import (
    Event,
    EventFoodPass,
    Payment,
    Refund,
    EventExpense,
    WorkflowState
)


db = SessionLocal()

event = db.query(Event).order_by(Event.created_at.desc()).first()

if not event:
    raise Exception("No event found")

# Delete transactional data ONLY
db.query(EventFoodPass).filter(EventFoodPass.event_id == event.id).delete()
db.query(Payment).filter(Payment.event_id == event.id).delete()
db.query(Refund).filter(Refund.event_id == event.id).delete()
db.query(EventExpense).filter(EventExpense.event_id == event.id).delete()

# Reset workflow
workflow = db.query(WorkflowState).filter(WorkflowState.event_id == event.id).first()
workflow.current_state = "DRAFT"
workflow.allowed_next_states = ["ACTIVE"]

event.status = "DRAFT"

db.commit()
db.close()

print("✅ Event reset to DRAFT (history preserved)")
